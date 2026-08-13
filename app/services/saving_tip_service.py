"""
Saving Tip service layer containing business logic for session-based household evaluation,
calculations, AI generation, and lifecycle management.
"""

import uuid
import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Tuple

from fastapi import HTTPException, status, BackgroundTasks
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import DEFAULT_RATE
from app.constants.saving_tip import (
    MINIMUM_APPLIANCES_FOR_TIPS,
    HIGH_SAVINGS_THRESHOLD_PHP,
    MEDIUM_SAVINGS_THRESHOLD_PHP,
    HIGH_MONTHLY_KWH_THRESHOLD,
    MEDIUM_MONTHLY_KWH_THRESHOLD,
)
from app.prompts.saving_tip import SAVING_TIP_SYSTEM_PROMPT
from app.database.models import (
    ApplianceInDB,
    SavingTipInDB,
    SavingTipSessionInDB,
    TipType,
    TipStatus,
    PriorityLevel,
    EffortLevel,
    AnalysisSessionStatus,
    ApplianceAnalysisStatus,
)
from app.schemas.saving_tip import (
    AISavingTipItem,
    ApplianceEvaluationItem,
    SavingTipResponse,
    SavingTipsSummaryResponse,
    HouseholdEvaluationResult,
    GenerateTipsResponse,
    HouseholdAnalysisStatusResponse,
)
from app.repositories.saving_tip import SavingTipRepository
from app.repositories.saving_tip_session import SavingTipSessionRepository
from app.repositories.appliance import ApplianceRepository
from app.repositories.user import UserRepository
from app.services.web_search_service import WebSearchService
from app.utils.household_snapshot import (
    generate_household_snapshot_version,
    format_cooldown_time_remaining,
)

logger = logging.getLogger(__name__)


@dataclass
class HouseholdAnalysisContext:
    """Internal context encapsulating state and inputs required during household analysis."""

    session_id: str
    user_id: str
    initial_snapshot_version: str
    electricity_rate: float
    active_appliances: List[ApplianceInDB]


class SavingTipService:
    """Service handling saving tip queries, session-based household evaluation, and AI generation"""

    def __init__(
        self,
        saving_tip_session_repo: SavingTipSessionRepository,
        saving_tip_repo: SavingTipRepository,
        appliance_repo: ApplianceRepository,
        user_repo: UserRepository,
        web_search_service: WebSearchService,
        model: BaseChatModel,
    ):
        self.saving_tip_session_repo = saving_tip_session_repo
        self.saving_tip_repo = saving_tip_repo
        self.appliance_repo = appliance_repo
        self.user_repo = user_repo
        self.web_search_service = web_search_service
        self.model = model

    def _to_response(self, tip: SavingTipInDB) -> SavingTipResponse:
        """Convert database model to API response model"""
        return SavingTipResponse(
            id=tip.id,
            user_id=tip.user_id,
            session_id=tip.session_id,
            appliance_id=tip.appliance_id,
            appliance_name=tip.appliance_name,
            appliance_category=tip.appliance_category,
            appliance_wattage_watts=tip.appliance_wattage_watts,
            appliance_daily_usage_hours=tip.appliance_daily_usage_hours,
            appliance_monthly_kwh=tip.appliance_monthly_kwh,
            title=tip.title,
            description=tip.description,
            priority=tip.priority,
            effort_level=tip.effort_level,
            recommended_daily_usage_reduction_hours=tip.recommended_daily_usage_reduction_hours,
            estimated_monthly_savings=tip.estimated_monthly_savings,
            tip_type=tip.tip_type,
            source_url=tip.source_url,
            source_name=tip.source_name,
            status=tip.status,
            generated_at=tip.generated_at,
            created_at=tip.created_at,
            updated_at=tip.updated_at,
        )

    def get_user_tips(self, user_id: str) -> List[SavingTipResponse]:
        """Retrieve saving tips associated with the latest completed analysis session for a user"""
        latest_completed = self.saving_tip_session_repo.get_latest_completed_session(
            user_id
        )
        if not latest_completed:
            return []

        tips = self.saving_tip_repo.get_tips_by_session(latest_completed.id, user_id)
        priority_order = {
            PriorityLevel.HIGH: 0,
            PriorityLevel.MEDIUM: 1,
            PriorityLevel.LOW: 2,
        }
        status_order = {
            TipStatus.ACTIVE: 0,
            TipStatus.COMPLETED: 1,
            TipStatus.OUTDATED: 2,
            TipStatus.STALE: 3,
        }
        tips.sort(
            key=lambda t: (
                status_order.get(t.status, 4),
                priority_order.get(t.priority, 3),
                -t.generated_at.timestamp(),
            )
        )
        return [self._to_response(t) for t in tips]

    def get_user_tips_summary(self, user_id: str) -> SavingTipsSummaryResponse:
        """Compute top summary card metrics for user's active saving tips"""
        tips = self.get_user_tips(user_id)
        active_tips = [t for t in tips if t.status == TipStatus.ACTIVE]

        total_potential_monthly_savings = sum(
            t.estimated_monthly_savings
            for t in active_tips
            if t.estimated_monthly_savings
        )
        total_yearly_savings = total_potential_monthly_savings * 12.0

        total_tips_count = len(tips)
        easy_wins_count = sum(1 for t in tips if t.effort_level == EffortLevel.LOW)

        active_appliances = self.appliance_repo.get_active_user_appliances(user_id)
        user = self.user_repo.get_by_id(user_id)
        electricity_rate = (
            user.settings.electricity_rate_php_kwh
            if user and user.settings
            else DEFAULT_RATE
        )

        total_monthly_kwh = sum(
            (app.wattage_watts / 1000.0) * app.daily_usage_hours * 30.0
            for app in active_appliances
        )
        total_monthly_cost = total_monthly_kwh * electricity_rate

        percentage_bill_reduction = (
            round(
                min(
                    (total_potential_monthly_savings / total_monthly_cost) * 100.0,
                    100.0,
                ),
                1,
            )
            if total_monthly_cost > 0
            else 0.0
        )

        return SavingTipsSummaryResponse(
            total_potential_monthly_savings=round(total_potential_monthly_savings, 2),
            total_yearly_savings=round(total_yearly_savings, 2),
            total_tips_count=total_tips_count,
            easy_wins_count=easy_wins_count,
            percentage_bill_reduction=percentage_bill_reduction,
        )

    def update_tip_status(
        self, user_id: str, tip_id: str, status_str: str
    ) -> SavingTipResponse:
        """Update status of a saving tip (active, completed, deleted)"""
        tip = self.saving_tip_repo.get_by_id_and_user(tip_id, user_id)
        if not tip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saving tip not found or access denied.",
            )

        if (
            tip.status in (TipStatus.STALE, TipStatus.OUTDATED)
            and status_str != TipStatus.DELETED.value
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Outdated or stale tips for modified or deleted appliances cannot be marked as completed.",
            )

        self.saving_tip_repo.update_status(tip_id, user_id, status_str)
        updated_tip = self.saving_tip_repo.get_by_id_and_user(tip_id, user_id)
        if not updated_tip:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated saving tip.",
            )

        return self._to_response(updated_tip)

    def get_analysis_status(self, user_id: str) -> HouseholdAnalysisStatusResponse:
        """Fetch current household analysis status, cooldown metadata, and snapshot versions"""
        appliances = self.appliance_repo.get_user_appliances(user_id)
        active_appliances = [app for app in appliances if app.is_active]

        current_snapshot = generate_household_snapshot_version(appliances)
        latest_session = self.saving_tip_session_repo.get_latest_session(user_id)
        latest_completed = self.saving_tip_session_repo.get_latest_completed_session(
            user_id
        )
        in_progress_session = (
            self.saving_tip_session_repo.get_active_in_progress_session(user_id)
        )

        now = datetime.now(timezone.utc)
        next_allowed = (
            latest_completed.next_allowed_analysis_at if latest_completed else None
        )

        # Fix naive vs timezone-aware datetime comparisons
        if next_allowed is not None and next_allowed.tzinfo is None:
            next_allowed = next_allowed.replace(tzinfo=timezone.utc)

        is_cooldown_active = bool(next_allowed and now < next_allowed)

        analyzed_snapshot = (
            latest_completed.household_snapshot_version if latest_completed else None
        )
        is_household_outdated = bool(
            latest_completed and current_snapshot != analyzed_snapshot
        )

        session_status = None
        if in_progress_session:
            session_status = AnalysisSessionStatus.IN_PROGRESS
        elif latest_session:
            session_status = latest_session.status

        return HouseholdAnalysisStatusResponse(
            session_status=session_status,
            is_cooldown_active=is_cooldown_active,
            is_household_outdated=is_household_outdated,
            current_household_snapshot_version=current_snapshot,
            analyzed_household_snapshot_version=analyzed_snapshot,
            next_allowed_analysis_at=next_allowed,
            active_appliance_count=len(active_appliances),
        )

    def start_household_analysis(
        self, user_id: str, background_tasks: BackgroundTasks
    ) -> GenerateTipsResponse:
        """
        Validates requirements and starts async household saving tips analysis.
        Returns immediately with session information (202 Accepted pattern).
        """
        appliances = self.appliance_repo.get_user_appliances(user_id)
        active_appliances = [app for app in appliances if app.is_active]

        # Minimum appliances check
        if len(active_appliances) < MINIMUM_APPLIANCES_FOR_TIPS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Household energy analysis requires at least "
                f"{MINIMUM_APPLIANCES_FOR_TIPS} active appliances.",
            )

        # Lock check: prevent concurrent IN_PROGRESS sessions
        in_progress = self.saving_tip_session_repo.get_active_in_progress_session(
            user_id
        )
        if in_progress:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A household energy analysis is already in progress.",
            )

        # Cooldown check: 24h cooldown after latest completed session
        latest_completed = self.saving_tip_session_repo.get_latest_completed_session(
            user_id
        )
        now = datetime.now(timezone.utc)
        if latest_completed and latest_completed.next_allowed_analysis_at:
            next_allowed = latest_completed.next_allowed_analysis_at
            if next_allowed.tzinfo is None:
                next_allowed = next_allowed.replace(tzinfo=timezone.utc)
            if now < next_allowed:
                time_left_str = format_cooldown_time_remaining(next_allowed, now)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"You can try again in {time_left_str}.",
                )

        initial_snapshot = generate_household_snapshot_version(appliances)
        session_id = str(uuid.uuid4())

        new_session = SavingTipSessionInDB(
            id=session_id,
            user_id=user_id,
            household_snapshot_version=initial_snapshot,
            active_appliance_count=len(active_appliances),
            status=AnalysisSessionStatus.IN_PROGRESS,
            started_at=now,
        )
        self.saving_tip_session_repo.create_session(new_session)

        # Enqueue background execution task
        background_tasks.add_task(
            self.run_household_analysis_async,
            session_id,
            user_id,
            initial_snapshot,
        )

        return GenerateTipsResponse(
            session_id=session_id,
            message="Household energy analysis started successfully.",
            status=AnalysisSessionStatus.IN_PROGRESS,
        )

    async def run_household_analysis_async(
        self, session_id: str, user_id: str, initial_snapshot_version: str
    ) -> None:
        """
        Async background worker executing Gemini evaluation, WebSearch, tip creation,
        appliance status updates, and session completion in an Ordered Completion Sequence.
        """
        logger.info(
            "Starting background household analysis session %s for user %s",
            session_id,
            user_id,
        )
        try:
            context = self._load_analysis_context(
                session_id, user_id, initial_snapshot_version
            )
            eval_result = await self._evaluate_household(context)

            if self._household_changed(context):
                self._mark_session_outdated(context)
                return

            generated_tips, evaluated_status_map = await self._build_saving_tips(
                context, eval_result
            )

            self._persist_analysis_results(
                context, generated_tips, evaluated_status_map
            )
            self._complete_session(context, len(generated_tips))

        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "Error executing household analysis session %s: %s",
                session_id,
                str(e),
            )
            self.saving_tip_session_repo.fail_session(session_id, user_id, str(e))

    def _load_analysis_context(
        self, session_id: str, user_id: str, initial_snapshot_version: str
    ) -> HouseholdAnalysisContext:
        """Load active appliances, user info, and electricity rate into a context object."""
        active_appliances = self.appliance_repo.get_active_user_appliances(user_id)
        user = self.user_repo.get_by_id(user_id)
        electricity_rate = (
            user.settings.electricity_rate_php_kwh
            if user and user.settings
            else DEFAULT_RATE
        )
        return HouseholdAnalysisContext(
            session_id=session_id,
            user_id=user_id,
            initial_snapshot_version=initial_snapshot_version,
            electricity_rate=electricity_rate,
            active_appliances=active_appliances,
        )

    def _build_household_prompt(self, context: HouseholdAnalysisContext) -> str:
        """Generate structured LLM prompt listing active appliances and electricity rate."""
        appliance_lines = []
        for app in context.active_appliances:
            monthly_kwh = (app.wattage_watts * app.daily_usage_hours * 30.0) / 1000.0
            appliance_lines.append(
                f"- Appliance ID: {app.id} | Name: {app.name} | Category: {app.category} | "
                f"Wattage: {app.wattage_watts}W "
                f"| Daily Usage: {app.daily_usage_hours} hrs/day | "
                f"Monthly Consumption: {monthly_kwh:.1f} kWh/month"
            )

        ecosystem_text = "\n".join(appliance_lines)
        return (
            f"HOUSEHOLD ELECTRICITY TARIFF RATE: ₱{context.electricity_rate}/kWh\n\n"
            f"ALL ACTIVE HOUSEHOLD APPLIANCES:\n"
            f"{ecosystem_text}\n\n"
            "Please evaluate all active appliances in the household as "
            "a whole and return structured evaluations."
        )

    async def _evaluate_household(
        self, context: HouseholdAnalysisContext
    ) -> HouseholdEvaluationResult:
        """Invoke Gemini with structured output for household evaluation."""
        user_prompt = self._build_household_prompt(context)
        structured_model = self.model.with_structured_output(HouseholdEvaluationResult)
        result = await structured_model.ainvoke(
            [
                SystemMessage(content=SAVING_TIP_SYSTEM_PROMPT),
                HumanMessage(content=user_prompt),
            ]
        )
        if isinstance(result, HouseholdEvaluationResult):
            return result
        if isinstance(result, dict):
            return HouseholdEvaluationResult.model_validate(result)
        raise ValueError(f"Unexpected LLM evaluation result type: {type(result)}")

    def _household_changed(self, context: HouseholdAnalysisContext) -> bool:
        """Check if current household snapshot differs from initial snapshot version."""
        all_appliances_now = self.appliance_repo.get_user_appliances(context.user_id)
        current_snapshot = generate_household_snapshot_version(all_appliances_now)
        return current_snapshot != context.initial_snapshot_version

    def _mark_session_outdated(self, context: HouseholdAnalysisContext) -> None:
        """Mark session as outdated due to household configuration changes."""
        logger.warning(
            "Household configuration changed during session %s. Marking session OUTDATED.",
            context.session_id,
        )
        self.saving_tip_session_repo.mark_session_outdated(
            context.session_id,
            context.user_id,
            "Household configuration changed during analysis",
        )

    async def _build_saving_tips(
        self,
        context: HouseholdAnalysisContext,
        eval_result: HouseholdEvaluationResult,
    ) -> Tuple[List[SavingTipInDB], Dict[str, ApplianceAnalysisStatus]]:
        """Iterate appliance evaluations, build saving tips and status map."""
        generated_tips: List[SavingTipInDB] = []
        evaluated_status_map: Dict[str, ApplianceAnalysisStatus] = {}

        if not eval_result or not eval_result.evaluations:
            return generated_tips, evaluated_status_map

        for app_eval in eval_result.evaluations:
            app_tips = await self._process_appliance_evaluation(
                context, app_eval, evaluated_status_map
            )
            generated_tips.extend(app_tips)

        return generated_tips, evaluated_status_map

    async def _process_appliance_evaluation(
        self,
        context: HouseholdAnalysisContext,
        app_eval: ApplianceEvaluationItem,
        evaluated_status_map: Dict[str, ApplianceAnalysisStatus],
    ) -> List[SavingTipInDB]:
        """Process evaluation for a single appliance and generate saving tip documents."""
        app_id = app_eval.appliance_id
        target_app = next(
            (a for a in context.active_appliances if a.id == app_id), None
        )
        if not target_app:
            return []

        evaluated_status_map[app_id] = app_eval.analysis_status

        if (
            app_eval.analysis_status != ApplianceAnalysisStatus.HAS_RECOMMENDATIONS
            or not app_eval.tips
        ):
            return []

        target_monthly_kwh = (
            target_app.wattage_watts * target_app.daily_usage_hours * 30.0
        ) / 1000.0

        tips: List[SavingTipInDB] = []
        for item in app_eval.tips:
            tip_doc = await self._create_tip_document(
                context, target_app, target_monthly_kwh, item
            )
            tips.append(tip_doc)

        return tips

    async def _create_tip_document(
        self,
        context: HouseholdAnalysisContext,
        target_app: ApplianceInDB,
        target_monthly_kwh: float,
        item: AISavingTipItem,
    ) -> SavingTipInDB:
        """
        Create a single SavingTipInDB document by calculating savings, priority, and resolving source.
        """
        estimated_monthly_savings, recommended_reduction, priority = (
            self._calculate_tip_savings_and_priority(
                context, target_app, target_monthly_kwh, item
            )
        )
        source_name, source_url = await self._resolve_source(target_app, item)

        return self._build_saving_tip_document(
            context=context,
            target_app=target_app,
            target_monthly_kwh=target_monthly_kwh,
            item=item,
            priority=priority,
            recommended_reduction=recommended_reduction,
            estimated_monthly_savings=estimated_monthly_savings,
            source_name=source_name,
            source_url=source_url,
        )

    def _calculate_tip_savings_and_priority(
        self,
        context: HouseholdAnalysisContext,
        target_app: ApplianceInDB,
        target_monthly_kwh: float,
        item: AISavingTipItem,
    ) -> Tuple[Optional[float], Optional[float], PriorityLevel]:
        """Calculate estimated monthly savings, recommended reduction, and priority for a tip."""
        estimated_monthly_savings: Optional[float] = None
        recommended_reduction: Optional[float] = None
        priority = PriorityLevel.LOW

        if item.tip_type == TipType.CALCULATED:
            (
                estimated_monthly_savings,
                recommended_reduction,
                priority,
            ) = self._calculate_calculated_tip_metrics(
                context.electricity_rate, target_app, item
            )
        elif item.tip_type == TipType.REFERENCE:
            priority = self._calculate_reference_tip_priority(target_monthly_kwh)

        return estimated_monthly_savings, recommended_reduction, priority

    def _calculate_calculated_tip_metrics(
        self,
        electricity_rate: float,
        target_app: ApplianceInDB,
        item: AISavingTipItem,
    ) -> Tuple[float, float, PriorityLevel]:
        """Calculate reduction hours, monthly PHP savings, and priority for CALCULATED tips."""
        reduction_hours = item.recommended_daily_usage_reduction_hours or 1.0
        clamped_reduction = min(
            max(0.1, reduction_hours),
            target_app.daily_usage_hours,
        )
        recommended_reduction = clamped_reduction
        kwh_saved = (target_app.wattage_watts / 1000.0) * clamped_reduction * 30.0
        savings = round(kwh_saved * electricity_rate, 2)
        estimated_monthly_savings = max(0.0, savings)

        if estimated_monthly_savings >= HIGH_SAVINGS_THRESHOLD_PHP:
            priority = PriorityLevel.HIGH
        elif estimated_monthly_savings >= MEDIUM_SAVINGS_THRESHOLD_PHP:
            priority = PriorityLevel.MEDIUM
        else:
            priority = PriorityLevel.LOW

        return estimated_monthly_savings, recommended_reduction, priority

    def _calculate_reference_tip_priority(
        self, target_monthly_kwh: float
    ) -> PriorityLevel:
        """Calculate priority for REFERENCE tips based on appliance monthly kWh consumption."""
        if target_monthly_kwh >= HIGH_MONTHLY_KWH_THRESHOLD:
            return PriorityLevel.HIGH
        elif target_monthly_kwh >= MEDIUM_MONTHLY_KWH_THRESHOLD:
            return PriorityLevel.MEDIUM
        else:
            return PriorityLevel.LOW

    async def _resolve_source(
        self, target_app: ApplianceInDB, item: AISavingTipItem
    ) -> Tuple[Optional[str], Optional[str]]:
        """Perform web search if required to resolve source name and URL for a tip."""
        if not item.requires_source:
            return None, None

        search_query = (
            item.source_query
            or f"Department of Energy {target_app.category} {target_app.name} energy efficiency"
        )
        try:
            search_res = await self.web_search_service.search(
                query=search_query, max_results=4
            )
            if search_res.success and search_res.data and search_res.data.results:
                quality_item = search_res.data.results[0]
                raw_title = quality_item.title or "Energy Reference"
                source_name = (
                    raw_title[:55] + "..." if len(raw_title) > 55 else raw_title
                )
                source_url = quality_item.url
                return source_name, source_url
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                "Web search failed for query %r: %s",
                search_query,
                str(e),
            )
        return None, None

    def _build_saving_tip_document(
        self,
        context: HouseholdAnalysisContext,
        target_app: ApplianceInDB,
        target_monthly_kwh: float,
        item: AISavingTipItem,
        priority: PriorityLevel,
        recommended_reduction: Optional[float],
        estimated_monthly_savings: Optional[float],
        source_name: Optional[str],
        source_url: Optional[str],
    ) -> SavingTipInDB:
        """Instantiate SavingTipInDB document for a generated tip."""
        return SavingTipInDB(
            id=str(uuid.uuid4()),
            user_id=context.user_id,
            session_id=context.session_id,
            appliance_id=target_app.id,
            appliance_name=target_app.name,
            appliance_category=target_app.category,
            appliance_wattage_watts=target_app.wattage_watts,
            appliance_daily_usage_hours=target_app.daily_usage_hours,
            appliance_monthly_kwh=target_monthly_kwh,
            title=item.title.strip(),
            description=item.description.strip(),
            priority=priority,
            effort_level=item.effort_level,
            recommended_daily_usage_reduction_hours=recommended_reduction,
            estimated_monthly_savings=estimated_monthly_savings,
            tip_type=item.tip_type,
            source_url=source_url,
            source_name=source_name,
            status=TipStatus.ACTIVE,
        )

    def _persist_analysis_results(
        self,
        context: HouseholdAnalysisContext,
        generated_tips: List[SavingTipInDB],
        evaluated_status_map: Dict[str, ApplianceAnalysisStatus],
    ) -> None:
        """Persist generated tips and bulk update appliance analysis statuses in MongoDB."""
        if generated_tips:
            self.saving_tip_repo.create_tips(generated_tips)

        self.appliance_repo.bulk_update_appliance_analysis_statuses(
            user_id=context.user_id,
            evaluated_status_map=evaluated_status_map,
            session_id=context.session_id,
        )

    def _complete_session(
        self, context: HouseholdAnalysisContext, tips_count: int
    ) -> None:
        """Mark analysis session as completed and schedule 24-hour cooldown."""
        next_allowed = datetime.now(timezone.utc) + timedelta(hours=24)
        self.saving_tip_session_repo.complete_session(
            session_id=context.session_id,
            user_id=context.user_id,
            tips_count=tips_count,
            next_allowed_analysis_at=next_allowed,
        )
        logger.info(
            "Successfully completed household analysis session %s with %d tips",
            context.session_id,
            tips_count,
        )
