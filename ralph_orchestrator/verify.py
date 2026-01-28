"""Verification engine for Ralph orchestrator.

Runs post-completion verification:
1. Quality gates (build, lint, test, type-check)
2. Service startup (backend, frontend)
3. UI tests (agent-browser, Robot Framework)
4. Fix loops for failures

Can be called standalone via `ralph verify` or at the end of `ralph run`.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional

from .config import RalphConfig, load_config
from .session import Session, create_session, load_session
from .timeline import TimelineLogger, create_timeline_logger, EventType
from .gates import GateRunner, create_gate_runner, GatesResult, format_gates_summary
# Import from services.py module (service lifecycle), not services/ package (orchestration)
from .service_lifecycle import ServiceManager, create_service_manager, ServiceResult, format_service_status
from .ui import (
    AgentBrowserRunner,
    RobotRunner,
    UITestSuiteResult,
    UITestResult,
    is_agent_browser_enabled,
    is_robot_enabled,
    create_agent_browser_runner,
    create_robot_runner,
    format_ui_test_summary,
    format_failure_description,
)
from .agents.claude import ClaudeRunner, create_claude_runner
from .agents.prompts import (
    AgentRole,
    build_ui_planning_prompt,
    build_ui_implementation_prompt,
    get_allowed_tools_for_role,
)
from .signals import validate_ui_plan_signal, validate_ui_fix_signal


class VerifyExitCode(int, Enum):
    """Exit codes for ralph verify."""
    SUCCESS = 0
    CONFIG_ERROR = 1
    GATE_FAILURE = 4
    UI_TEST_FAILURE = 5
    ROBOT_TEST_FAILURE = 6
    SERVICE_FAILURE = 9


@dataclass
class VerifyOptions:
    """Options for the verify command."""
    gate_type: str = "full"
    run_ui: Optional[bool] = None  # None = use config default
    run_robot: Optional[bool] = None  # None = use config default
    env: str = "dev"
    fix: bool = False
    fix_iterations: int = 10
    skip_services: bool = False
    base_url: Optional[str] = None
    verbose: bool = False


@dataclass
class VerifyResult:
    """Result of verification run."""
    exit_code: VerifyExitCode
    gates_result: Optional[GatesResult] = None
    services_started: bool = False
    agent_browser_result: Optional[UITestSuiteResult] = None
    robot_result: Optional[UITestSuiteResult] = None
    fix_iterations: int = 0
    total_duration_ms: int = 0
    error: Optional[str] = None
    
    @property
    def all_passed(self) -> bool:
        """Check if all verification passed."""
        if self.gates_result and not self.gates_result.passed:
            return False
        if self.agent_browser_result and not self.agent_browser_result.passed:
            return False
        if self.robot_result and not self.robot_result.passed:
            return False
        return True


class VerifyEngine:
    """Main verification engine.
    
    Runs gates, starts services, executes UI tests, and handles fix loops.
    """
    
    def __init__(
        self,
        config: RalphConfig,
        session: Session,
        timeline: TimelineLogger,
        gate_runner: GateRunner,
        service_manager: ServiceManager,
        claude_runner: Optional[ClaudeRunner],
        options: VerifyOptions,
    ):
        """Initialize verification engine.
        
        Args:
            config: Ralph configuration.
            session: Session manager.
            timeline: Timeline logger.
            gate_runner: Gate execution runner.
            service_manager: Service lifecycle manager.
            claude_runner: Claude CLI runner (for fix loops).
            options: Verification options.
        """
        self.config = config
        self.session = session
        self.timeline = timeline
        self.gates = gate_runner
        self.services = service_manager
        self.claude = claude_runner
        self.options = options
        
        # Determine what UI tests to run
        self.run_agent_browser = self.options.run_ui
        if self.run_agent_browser is None:
            self.run_agent_browser = is_agent_browser_enabled(config)
        
        self.run_robot = self.options.run_robot
        if self.run_robot is None:
            self.run_robot = is_robot_enabled(config)
    
    def _print(self, msg: str, end: str = "\n") -> None:
        """Print message to stdout."""
        print(msg, end=end, file=sys.stdout, flush=True)
    
    def _run_gates(self) -> GatesResult:
        """Run quality gates.
        
        Returns:
            GatesResult with all gate outcomes.
        """
        gate_type = self.options.gate_type
        if gate_type == "none":
            return GatesResult(gate_type="none", passed=True)
        
        self._print(f"▶ Running quality gates ({gate_type})...")
        
        result = self.gates.run_gates(gate_type=gate_type)
        
        for gate_result in result.results:
            if gate_result.skipped:
                self._print(f"  ⊘ {gate_result.name} (skipped)")
            elif gate_result.passed:
                self._print(f"  ✓ {gate_result.name} ({gate_result.duration_ms / 1000:.1f}s)")
            else:
                self._print(f"  ✗ {gate_result.name} (failed)")
        
        return result
    
    def _start_services(self) -> bool:
        """Start backend and frontend services.
        
        Returns:
            True if all services started successfully.
        """
        self._print("\n▶ Starting services...")
        
        results = self.services.start_all(build_frontend=(self.options.env == "prod"))
        
        all_success = True
        for name, result in results.items():
            if result.success:
                self._print(f"  ✓ {name.capitalize()} ready on {result.url} ({result.duration_ms}ms)")
            else:
                self._print(f"  ✗ {name.capitalize()} failed: {result.error}")
                all_success = False
        
        return all_success
    
    def _get_base_url(self) -> Optional[str]:
        """Get base URL for UI tests."""
        if self.options.base_url:
            return self.options.base_url
        return self.services.get_base_url()
    
    def _run_agent_browser_tests(self, base_url: str) -> UITestSuiteResult:
        """Run agent-browser UI tests.
        
        Args:
            base_url: Base URL for tests.
            
        Returns:
            UITestSuiteResult with all test outcomes.
        """
        self._print("\n▶ Running UI tests (agent-browser)...")
        
        runner = create_agent_browser_runner(
            config=self.config,
            base_url=base_url,
            session_dir=self.session.session_dir,
            timeline=self.timeline,
        )
        
        result = runner.run()
        
        for test in result.results:
            if test.passed:
                self._print(f"  ✓ {test.name} ({test.duration_ms}ms)")
            else:
                self._print(f"  ✗ {test.name}")
                if test.error:
                    self._print(f"    {test.error}")
                if test.screenshot_path:
                    self._print(f"    Screenshot: {test.screenshot_path}")
        
        return result
    
    def _run_robot_tests(self, base_url: str) -> UITestSuiteResult:
        """Run Robot Framework tests.
        
        Args:
            base_url: Base URL for tests.
            
        Returns:
            UITestSuiteResult with all test outcomes.
        """
        self._print("\n▶ Running Robot Framework tests...")
        
        runner = create_robot_runner(
            config=self.config,
            base_url=base_url,
            session_dir=self.session.session_dir,
            timeline=self.timeline,
        )
        
        result = runner.run()
        
        for test in result.results:
            if test.passed:
                self._print(f"  ✓ {test.name} ({test.duration_ms}ms)")
            else:
                self._print(f"  ✗ {test.name}")
                if test.error:
                    self._print(f"    {test.error}")
        
        return result
    
    def _run_ui_fix_loop(
        self,
        failures: List[UITestResult],
        framework: str,
        base_url: str,
    ) -> bool:
        """Run fix loop for UI test failures.

        Uses plan→implement→retest pattern.

        Args:
            failures: List of failed test results.
            framework: Test framework name.
            base_url: Base URL for tests.

        Returns:
            True if all failures were fixed.
        """
        if not self.claude or not failures:
            return False

        # Ensure session token is available
        session_token = self.session.session_token
        if not session_token:
            self._print("    ✗ No session token available for fix loop")
            return False

        max_iterations = self.options.fix_iterations

        # Log fix loop start
        self.timeline.fix_loop_start(framework, max_iterations)
        
        for iteration in range(1, max_iterations + 1):
            self._print(f"\n  Fix iteration {iteration}/{max_iterations}...")
            
            # Create failure description
            failure_descriptions = []
            for failure in failures:
                desc = format_failure_description(failure, framework)
                failure_descriptions.append(desc)
            
            combined_failures = "\n\n---\n\n".join(failure_descriptions)
            
            # Run planning agent
            self._print("    ▶ Planning agent analyzing failures...")
            plan_prompt = build_ui_planning_prompt(
                failure_description=combined_failures,
                session_token=session_token,
            )
            
            agent_config = self.config.get_agent_config("planning")
            plan_result = self.claude.invoke(
                prompt=plan_prompt,
                role="ui_planning",
                model=agent_config.model,
                allowed_tools=get_allowed_tools_for_role(AgentRole.UI_PLANNING),
                timeout=agent_config.timeout,
            )
            
            if not plan_result.success:
                self._print(f"    ✗ Planning failed: {plan_result.error}")
                self.timeline.fix_loop_iteration(framework, iteration, "planning_failed")
                continue
            
            # Validate plan signal
            plan_validation = validate_ui_plan_signal(plan_result.output, session_token)
            if not plan_validation.valid:
                self._print("    ✗ Planning agent did not provide valid plan signal")
                self.timeline.fix_loop_iteration(framework, iteration, "invalid_plan_signal")
                continue
            
            plan_content = plan_validation.signal.content if plan_validation.signal else plan_result.output
            
            # Run implementation agent
            self._print("    ▶ Implementation agent applying fixes...")
            impl_prompt = build_ui_implementation_prompt(
                plan=plan_content,
                session_token=session_token,
            )
            
            impl_config = self.config.get_agent_config("implementation")
            impl_result = self.claude.invoke(
                prompt=impl_prompt,
                role="ui_implementation",
                model=impl_config.model,
                allowed_tools=get_allowed_tools_for_role(AgentRole.UI_IMPLEMENTATION),
                timeout=impl_config.timeout,
            )
            
            if not impl_result.success:
                self._print(f"    ✗ Implementation failed: {impl_result.error}")
                self.timeline.fix_loop_iteration(framework, iteration, "implementation_failed")
                continue
            
            # Validate fix signal
            fix_validation = validate_ui_fix_signal(impl_result.output, session_token)
            if not fix_validation.valid:
                self._print("    ✗ Implementation agent did not provide valid fix signal")
                self.timeline.fix_loop_iteration(framework, iteration, "invalid_fix_signal")
                continue
            
            # Retest
            self._print("    ▶ Retesting...")
            if framework == "agent_browser":
                retest_result = self._run_agent_browser_tests(base_url)
            else:
                retest_result = self._run_robot_tests(base_url)
            
            if retest_result.passed:
                self._print("    ✓ All tests pass after fix!")
                self.timeline.fix_loop_end(framework, success=True, iterations=iteration)
                return True
            
            # Update failures for next iteration
            failures = retest_result.get_failures()
            self.timeline.fix_loop_iteration(framework, iteration, "tests_still_failing")
            self._print(f"    ✗ {len(failures)} test(s) still failing")
        
        self.timeline.fix_loop_end(framework, success=False, iterations=max_iterations)
        return False
    
    def run(self) -> VerifyResult:
        """Execute verification.
        
        Returns:
            VerifyResult with overall outcome.
        """
        start_time = time.time()
        
        self._print("=" * 60)
        self._print("  RALPH VERIFICATION")
        self._print("=" * 60)
        
        # Phase 1: Quality Gates
        gates_result = self._run_gates()
        
        if not gates_result.passed:
            duration_ms = int((time.time() - start_time) * 1000)
            self._print(f"\n✗ Gate failure - verification stopped")
            return VerifyResult(
                exit_code=VerifyExitCode.GATE_FAILURE,
                gates_result=gates_result,
                total_duration_ms=duration_ms,
                error="Gate failure",
            )
        
        # Phase 2: Service Startup (unless skipped)
        services_started = False
        if not self.options.skip_services and (self.run_agent_browser or self.run_robot):
            services_started = self._start_services()
            if not services_started:
                # Try to get base_url anyway (maybe services are already running)
                if not self.options.base_url:
                    duration_ms = int((time.time() - start_time) * 1000)
                    self._print("\n✗ Service startup failed - verification stopped")
                    self.services.stop_all()
                    return VerifyResult(
                        exit_code=VerifyExitCode.SERVICE_FAILURE,
                        gates_result=gates_result,
                        services_started=False,
                        total_duration_ms=duration_ms,
                        error="Service startup failed",
                    )
        
        # Get base URL
        base_url = self._get_base_url()
        
        # Phase 3: UI Tests
        agent_browser_result = None
        robot_result = None
        fix_iterations = 0
        
        try:
            if self.run_agent_browser and base_url:
                agent_browser_result = self._run_agent_browser_tests(base_url)
                
                # Fix loop if enabled and there are failures
                if not agent_browser_result.passed and self.options.fix:
                    failures = agent_browser_result.get_failures()
                    if self._run_ui_fix_loop(failures, "agent_browser", base_url):
                        # Re-run to get updated result
                        agent_browser_result = self._run_agent_browser_tests(base_url)
                        fix_iterations += 1
            
            if self.run_robot and base_url:
                robot_result = self._run_robot_tests(base_url)
                
                # Fix loop if enabled and there are failures
                if not robot_result.passed and self.options.fix:
                    failures = robot_result.get_failures()
                    if self._run_ui_fix_loop(failures, "robot", base_url):
                        # Re-run to get updated result
                        robot_result = self._run_robot_tests(base_url)
                        fix_iterations += 1
        finally:
            # Always clean up services
            if services_started:
                self._print("\n▶ Stopping services...")
                self.services.stop_all()
        
        # Calculate final result
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Determine exit code
        exit_code = VerifyExitCode.SUCCESS
        error = None
        
        if agent_browser_result and not agent_browser_result.passed:
            exit_code = VerifyExitCode.UI_TEST_FAILURE
            error = "UI test failures"
        
        if robot_result and not robot_result.passed:
            exit_code = VerifyExitCode.ROBOT_TEST_FAILURE
            error = "Robot Framework test failures"
        
        # Print summary
        self._print("\n" + "=" * 60)
        if exit_code == VerifyExitCode.SUCCESS:
            self._print("  RESULT: ALL VERIFICATION PASSED")
        else:
            self._print("  RESULT: VERIFICATION FAILED")
        self._print("=" * 60)
        
        self._print(f"  Gates: {gates_result.passed_count}/{len(gates_result.results)} passed")
        
        if agent_browser_result:
            self._print(f"  UI Tests: {agent_browser_result.passed_count}/{len(agent_browser_result.results)} passed")
        
        if robot_result:
            self._print(f"  Robot Tests: {robot_result.passed_count}/{len(robot_result.results)} passed")
        
        self._print(f"  Duration: {duration_ms // 1000}s")
        
        if fix_iterations > 0:
            self._print(f"  Fix iterations: {fix_iterations}")
        
        if not (exit_code == VerifyExitCode.SUCCESS) and self.options.fix:
            self._print("\n  Run with --fix to attempt automatic repair.")
        
        return VerifyResult(
            exit_code=exit_code,
            gates_result=gates_result,
            services_started=services_started,
            agent_browser_result=agent_browser_result,
            robot_result=robot_result,
            fix_iterations=fix_iterations,
            total_duration_ms=duration_ms,
            error=error,
        )


def run_verify(
    config_path: Optional[Path] = None,
    options: Optional[VerifyOptions] = None,
) -> VerifyResult:
    """Main entry point for verification.
    
    Args:
        config_path: Path to ralph.yml configuration.
        options: Verification options.
        
    Returns:
        VerifyResult with verification outcome.
    """
    options = options or VerifyOptions()
    
    # Load configuration
    try:
        config = load_config(config_path)
    except (FileNotFoundError, ValueError) as e:
        return VerifyResult(
            exit_code=VerifyExitCode.CONFIG_ERROR,
            error=str(e),
        )
    
    # Setup session (create new for verify-only runs)
    session = create_session(
        task_source="verify",
        task_source_type="verify",
        config_path=str(config.path) if config.path else None,
        pending_tasks=[],
        repo_root=config.repo_root,
    )
    
    # Setup components
    timeline = create_timeline_logger(session.session_dir, session.session_id)
    gate_runner = create_gate_runner(config, config.repo_root, session.logs_dir, timeline)
    service_manager = create_service_manager(
        config=config,
        session_dir=session.session_dir,
        env=options.env,
        timeline=timeline,
    )
    
    # Setup Claude runner for fix loops (optional)
    claude_runner = None
    if options.fix:
        claude_runner = create_claude_runner(config, session.logs_dir, timeline, config.repo_root)
    
    # Create and run engine
    engine = VerifyEngine(
        config=config,
        session=session,
        timeline=timeline,
        gate_runner=gate_runner,
        service_manager=service_manager,
        claude_runner=claude_runner,
        options=options,
    )
    
    try:
        result = engine.run()
    finally:
        # End session
        status = "completed" if result.exit_code == VerifyExitCode.SUCCESS else "failed"
        session.end_session(status)
    
    return result


def run_post_verify(
    config: RalphConfig,
    session: Session,
    timeline: TimelineLogger,
    options: Optional[VerifyOptions] = None,
) -> VerifyResult:
    """Run verification as part of ralph run (post-completion).
    
    Uses existing session and timeline.
    
    Args:
        config: Ralph configuration.
        session: Existing session.
        timeline: Existing timeline logger.
        options: Verification options.
        
    Returns:
        VerifyResult with verification outcome.
    """
    options = options or VerifyOptions()
    
    # Setup components
    gate_runner = create_gate_runner(config, config.repo_root, session.logs_dir, timeline)
    service_manager = create_service_manager(
        config=config,
        session_dir=session.session_dir,
        env=options.env,
        timeline=timeline,
    )
    
    # Setup Claude runner for fix loops
    claude_runner = None
    if options.fix:
        claude_runner = create_claude_runner(config, session.logs_dir, timeline, config.repo_root)
    
    # Create and run engine
    engine = VerifyEngine(
        config=config,
        session=session,
        timeline=timeline,
        gate_runner=gate_runner,
        service_manager=service_manager,
        claude_runner=claude_runner,
        options=options,
    )
    
    return engine.run()
