import traceback
import inspect
from opcode import opname


__all__ = ["NameNotFound", "get_var_name", "get_src_loc"]


class NameNotFound(Exception):
    pass


def get_var_name(depth=2):
    frame = inspect.currentframe()
    for _ in range(depth):
        frame = frame.f_back

    code = frame.f_code
    call_index = frame.f_lasti
    call_opc   = opname[code.co_code[call_index]]
    if call_opc not in ("CALL_FUNCTION", "CALL_FUNCTION_KW", "CALL_FUNCTION_EX", "CALL_METHOD"):
        return None

    index = call_index + 2
    while True:
        opc = opname[code.co_code[index]]
        if opc in ("STORE_NAME", "STORE_ATTR"):
            name_index = int(code.co_code[index + 1])
            return code.co_names[name_index]
        elif opc == "STORE_FAST":
            name_index = int(code.co_code[index + 1])
            return code.co_varnames[name_index]
        elif opc == "STORE_DEREF":
            name_index = int(code.co_code[index + 1])
            return code.co_cellvars[name_index]
        elif opc in ("LOAD_GLOBAL", "LOAD_ATTR", "LOAD_FAST", "LOAD_DEREF",
                     "DUP_TOP", "BUILD_LIST"):
            index += 2
        else:
            raise NameNotFound


def get_src_loc(src_loc_at=0):
    # n-th  frame: get_src_loc()
    # n-1th frame: caller of get_src_loc() (usually constructor)
    # n-2th frame: caller of caller (usually user code)
    # Python returns the stack frames reversed, so it is enough to set limit and grab the very
    # first one in the array.
    tb = traceback.extract_stack(limit=3 + src_loc_at)
    return (tb[0].filename, tb[0].lineno)
