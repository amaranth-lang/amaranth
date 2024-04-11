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
    if call_opc not in ("CALL_FUNCTION", "CALL_FUNCTION_KW", "CALL_FUNCTION_EX",
                        "CALL_METHOD", "CALL_METHOD_KW", "CALL", "CALL_KW"):
        if default is _raise_exception:
            raise NameNotFound
        else:
            return default

    index = call_index + 2
    imm = 0
    while True:
        opc = opname[code.co_code[index]]
        if opc == 'EXTENDED_ARG':
            imm |= int(code.co_code[index + 1])
            imm <<= 8
            index += 2
        elif opc in ("STORE_NAME", "STORE_ATTR"):
            imm |= int(code.co_code[index + 1])
            return code.co_names[imm]
        elif opc == "STORE_FAST":
            imm |= int(code.co_code[index + 1])
            if sys.version_info >= (3, 11):
                return code._varname_from_oparg(imm)
            else:
                return code.co_varnames[imm]
        elif opc == "STORE_DEREF":
            imm |= int(code.co_code[index + 1])
            if sys.version_info >= (3, 11):
                return code._varname_from_oparg(imm)
            else:
                if imm < len(code.co_cellvars):
                    return code.co_cellvars[imm]
                else:
                    return code.co_freevars[imm - len(code.co_cellvars)]
        elif opc in ("LOAD_GLOBAL", "LOAD_NAME", "LOAD_ATTR", "LOAD_FAST", "LOAD_DEREF",
                     "DUP_TOP", "BUILD_LIST", "CACHE", "COPY"):
            imm = 0
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
