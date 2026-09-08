/* x87trans integration for Bochs' existing x87 instruction machinery.
 * Included by fpu_trans.cc after cpu.h and the x87 declarations. Bochs owns
 * pending checks, stack faults, ES/B, instruction pointers and fault delivery.
 * The library owns arithmetic results, flags, C1/C2 and writeback decisions.
 */
#include <x87trans/x87trans.h>

bool BX_CPU_C::FPU_x87trans(bxInstruction_c *i, unsigned operation)
{
  struct library_context {
    x87t_context *value;
    library_context() : value(x87t_create()) {}
    ~library_context() { x87t_destroy(value); }
  };
  static const library_context context;
  if (!context.value) {
    BX_PANIC(("x87trans context allocation failed"));
    return false;
  }
  const unsigned precision[] = {24, 0, 53, 64};
  Bit16u cw = BX_CPU_THIS_PTR the_i387.get_control_word();
  x87t_control control = {
    (x87t_round)((cw >> 10) & 3), precision[(cw >> 8) & 3], (uint8_t)(cw & 63)
  };
  floatx80 st0 = BX_READ_FPU_REG(0);
  x87t_raw80 x = {st0.signExp, st0.signif}, y = {0, 0};
  if (operation >= 5) {
    floatx80 st1 = BX_READ_FPU_REG(1);
    y = x87t_raw80{st1.signExp, st1.signif};
  }
  x87t_result result;
  x87t_error error;
  switch (operation) {
    case 0: error = x87t_fsin(context.value, x, &control, &result); break;
    case 1: error = x87t_fcos(context.value, x, &control, &result); break;
    case 2: error = x87t_fsincos(context.value, x, &control, &result); break;
    case 3: error = x87t_fptan(context.value, x, &control, &result); break;
    case 4: error = x87t_f2xm1(context.value, x, &control, &result); break;
    case 5: error = x87t_fpatan(context.value, y, x, &control, &result); break;
    case 6: error = x87t_fyl2x(context.value, y, x, &control, &result); break;
    case 7: error = x87t_fyl2xp1(context.value, y, x, &control, &result); break;
    default: return false;
  }
  // Undefined numerical domains and reserved controls retain Bochs' policy.
  if (error == X87T_OUTSIDE_SCOPE || error == X87T_UNSUPPORTED_CONTROL)
    return false;
  if (error != X87T_OK || result.exceptions_known != 63) {
    BX_PANIC(("incomplete x87trans result"));
    return false;
  }
  FPU_exception(i, result.exceptions);
  FPU_PARTIAL_STATUS = (FPU_PARTIAL_STATUS & ~result.cc_known) |
                      (result.cc & result.cc_known);
  if (result.completion == X87T_UNMASKED_NO_WRITE ||
      result.completion == X87T_RANGE_RETURN)
    return true;

  floatx80 primary = packFloatx80(result.primary.se >> 15,
                                  result.primary.se & 0x7fff, result.primary.sig);
  switch (result.destination) {
    case X87T_REPLACE_ST0:
      BX_WRITE_FPU_REG(primary, 0);
      break;
    case X87T_REPLACE_ST0_PUSH: {
      floatx80 pushed = packFloatx80(result.pushed.se >> 15,
                                     result.pushed.se & 0x7fff, result.pushed.sig);
      BX_WRITE_FPU_REG(primary, 0);
      BX_CPU_THIS_PTR the_i387.FPU_push();
      BX_WRITE_FPU_REG(pushed, 0);
      break;
    }
    case X87T_REPLACE_ST1_POP:
      BX_CPU_THIS_PTR the_i387.FPU_pop();
      BX_WRITE_FPU_REG(primary, 0);
      break;
    default:
      BX_PANIC(("invalid x87trans destination"));
  }
  return true;
}
