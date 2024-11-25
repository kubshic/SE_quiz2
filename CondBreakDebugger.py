import sys
from types import FrameType
from typing import TextIO, Set, Dict, Any, Optional, Callable
from utils import next_inputs


class CondBreakDebugger:
    """Interactive Debugger"""

    def __init__(self, *, file: TextIO = sys.stdout) -> None:
        self.stepping: bool = True
        self.breakpoints: Set[int] = set()
        self.conditional_breakpoints: Dict[str, int] = {}
        self.interact: bool = True

        self.frame: Optional[FrameType] = None
        self.event: Optional[str] = None
        self.arg: Any = None

        self.local_vars: Dict[str, Any] = {}

        self.file = file

    def __enter__(self):
        sys.settrace(self.traceit)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        sys.settrace(None)

    def log(self, *args):
        print(*args, file=self.file)

    def traceit(self, frame: FrameType, event: str, arg: Any) -> None:
        """Tracing function; called at every line."""
        self.event = event
        self.arg = arg

        if event == "call":
            # 함수 호출 시 프레임 설정
            self.frame = frame
            self.local_vars = frame.f_locals.copy()  # 현재 프레임의 로컬 변수 복사
        elif event == "line":
            # 각 라인 실행 시 프레임 업데이트
            self.frame = frame
            self.local_vars = frame.f_locals.copy()

        if self.stop_here():
            self.interaction_loop()


    def stop_here(self) -> bool:
        """Return True if we should stop."""
        for cond in self.conditional_breakpoints.keys():
            try:
                # 조건 평가: frame.f_locals를 기반으로 조건 평가
                if eval(cond, globals(), self.frame.f_locals):
                    self.conditional_breakpoints[cond] += 1
                    self.log(f"Conditional breakpoint triggered: {cond}")
                    return True
            except NameError as e:
                # # 평가 실패 시 로그 출력
                # self.log(f"Variable missing for condition '{cond}': {e}")
                continue
            except Exception as e:
                self.log(f"Error evaluating condition '{cond}': {e}")
        return self.stepping or self.frame.f_lineno in self.breakpoints




    def interaction_loop(self) -> None:
        """Interact with the user."""
        self.log(f"Paused at line {self.frame.f_lineno}, locals: {self.frame.f_locals}")
        self.interact = True
        while self.interact:
            try:
                command = next_inputs().pop(0)
                self.log(f"(debugger) {command}")
                self.execute(command)
            except IndexError:
                self.log("No more test inputs available. Exiting.")
                self.interact = False


    def step_command(self, arg: str = "") -> None:
        self.stepping = True
        self.interact = False

    def continue_command(self, arg: str = "") -> None:
        self.stepping = False
        self.interact = False

    def break_command(self, arg: str = "") -> None:
        if not arg:
            self.log("Breakpoints:", self.breakpoints)
            self.log("Conditional Breakpoints:", list(self.conditional_breakpoints.keys()))
        elif arg.isdigit():
            self.breakpoints.add(int(arg))
            self.log(f"Breakpoint set at line {arg}")
        else:
            self.conditional_breakpoints[arg] = 0
            self.log(f"Conditional breakpoint set: {arg}")

    def attr_command(self, arg: str) -> None:
        try:
            obj, var, expr = map(str.strip, arg.split(","))
            obj_eval = eval(obj, globals(), self.local_vars)
            value = eval(expr, globals(), self.local_vars)
            setattr(obj_eval, var, value)
            self.log(f"Set {var} of {obj} to {value}")
        except Exception as e:
            self.log(f"Error in attr command: {e}")

    def set_command(self, arg: str) -> None:
        """Set a local variable."""
        try:
            var, value = map(str.strip, arg.split("="))
            evaluated_value = eval(value, globals(), self.local_vars)
            if var in self.frame.f_locals:
                self.frame.f_locals[var] = evaluated_value
            else:
                self.local_vars[var] = evaluated_value
            self.log(f"Set local variable {var} to {evaluated_value}")
        except Exception as e:
            self.log(f"Error in set command: {e}")


    def execute(self, command: str) -> None:
        sep = command.find(' ')
        if sep > 0:
            cmd = command[:sep].strip()
            arg = command[sep + 1:].strip()
        else:
            cmd = command.strip()
            arg = ""

        method = self.command_method(cmd)
        if method:
            method(arg)
        else:
            self.log(f"Unknown command: {cmd}")

    def command_method(self, command: str) -> Optional[Callable[[str], None]]:
        possible_cmds = [possible_cmd for possible_cmd in self.commands()
                         if possible_cmd.startswith(command)]
        if len(possible_cmds) != 1:
            return None
        cmd = possible_cmds[0]
        return getattr(self, cmd + '_command')

    def commands(self) -> Set[str]:
        return {method.replace('_command', '') for method in dir(self)
                if method.endswith('_command')}

    def get_cond_break_map(self) -> Dict[str, int]:
        return {cond: count for cond, count in self.conditional_breakpoints.items() if count > 0}
