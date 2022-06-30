import sys
from opcode import opname


__all__ = ["NameNotFound", "get_var_name", "get_src_loc"]


class NameNotFound(Exception):
    pass


_raise_exception = object()


def get_var_name(depth=2, default=_raise_exception):
    frame = sys._getframe(depth)
    code = frame.f_code
    call_index = frame.f_lasti
    while call_index > 0 and opname[code.co_code[call_index]] == "CACHE":
        call_index -= 2
    while True:
        call_opc = opname[code.co_code[call_index]]
        if call_opc in ("EXTENDED_ARG",):
            call_index += 2
        else:
            break
    if call_opc not in ("CALL_FUNCTION", "CALL_FUNCTION_KW", "CALL_FUNCTION_EX", "CALL_METHOD", "CALL"):
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
            if sys.version_info >= (3, 11):
                name_index -= code.co_nlocals
            return code.co_cellvars[name_index]
        elif opc in ("LOAD_GLOBAL", "LOAD_NAME", "LOAD_ATTR", "LOAD_FAST", "LOAD_DEREF",
                     "DUP_TOP", "BUILD_LIST", "CACHE", "COPY"):
            index += 2
        else:
            if default is _raise_exception:
                raise NameNotFound
            else:
                return default


def get_src_loc(src_loc_at=0):
    # n-th  frame: get_src_loc()
    # n-1th frame: caller of get_src_loc() (usually constructor)
    # n-2th frame: caller of caller (usually user code)
    frame = sys._getframe(2 + src_loc_at)
    return (frame.f_code.co_filename, frame.f_lineno)
