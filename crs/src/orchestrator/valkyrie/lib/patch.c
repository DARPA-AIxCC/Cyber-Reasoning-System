
#include <assert.h>
#include <errno.h>
#include <ctype.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static bool log = false;

/****************************************************************************/
/* E9TOOL STATE STRUCTURE                                                   */
/****************************************************************************/

typedef struct
{
    union
    {
        uint16_t rflags;
        uint64_t __padding;
    };
    union
    {
        int64_t r15;
        int32_t r15d;
        int16_t r15w;
        int8_t r15b;
    };
    union
    {
        int64_t r14;
        int32_t r14d;
        int16_t r14w;
        int8_t r14b;
    };
    union
    {
        int64_t r13;
        int32_t r13d;
        int16_t r13w;
        int8_t r13b;
    };
    union
    {
        int64_t r12;
        int32_t r12d;
        int16_t r12w;
        int8_t r12b;
    };
    union
    {
        int64_t r11;
        int32_t r11d;
        int16_t r11w;
        int8_t r11b;
    };
    union
    {
        int64_t r10;
        int32_t r10d;
        int16_t r10w;
        int8_t r10b;
    };
    union
    {
        int64_t r9;
        int32_t r9d;
        int16_t r9w;
        int8_t r9b;
    };
    union
    {
        int64_t r8;
        int32_t r8d;
        int16_t r8w;
        int8_t r8b;
    };
    union
    {
        int64_t rdi;
        int32_t edi;
        int16_t di;
        int8_t dil;
    };
    union
    {
        int64_t rsi;
        int32_t esi;
        int16_t si;
        int8_t sil;
    };
    union
    {
        int64_t rbp;
        int32_t ebp;
        int16_t bp;
        int8_t bpl;
    };
    union
    {
        int64_t rbx;
        int32_t ebx;
        int16_t bx;
        struct
        {
            int8_t bl;
            int8_t bh;
        };
    };
    union
    {
        int64_t rdx;
        int32_t edx;
        int16_t dx;
        struct
        {
            int8_t dl;
            int8_t dh;
        };
    };
    union
    {
        int64_t rcx;
        int32_t ecx;
        int16_t cx;
        struct
        {
            int8_t cl;
            int8_t ch;
        };
    };
    union
    {
        int64_t rax;
        int32_t eax;
        int16_t ax;
        struct
        {
            int8_t al;
            int8_t ah;
        };
    };
    union
    {
        int64_t rsp;
        int32_t esp;
        int16_t sp;
        int16_t spl;
    };
    const union
    {
        int64_t rip;
        int32_t eip;
        int16_t ip;
    };
} STATE;

/****************************************************************************/
/* SUPER SIMPLE EXPRESSION PARSER+EVALUATOR:                                */
/****************************************************************************/

#define MAX_TOKEN       256

#define MAX(x, y)       ((x) > (y)? (x): (y))

typedef __int128 int128_t;

typedef enum
{
    TYPE_INTEGER,
    TYPE_BOOL,
    TYPE_CHAR,
    TYPE_INT8,
    TYPE_UINT8,
    TYPE_INT16,
    TYPE_UINT16,
    TYPE_INT32,
    TYPE_UINT32,
    TYPE_INT64,
    TYPE_UINT64,
    TYPE_PTR,
    TYPE_UNKNOWN = -1,
    TYPE_ERROR = -2
} TYPE;

#define TOKEN_ERROR     -1
#define TOKEN_END       1000
#define TOKEN_NAME      1001
#define TOKEN_INTEGER   1002
typedef int TOKEN;

struct var_s
{
    TYPE type;
    const char *name;
    void *ptr;
    struct var_s *next;
};
typedef struct var_s VAR;

typedef struct
{
    STATE *state;
    VAR *vars;
} CONTEXT;

typedef struct
{
    TYPE type;
    union
    {
        char c;
        int8_t i8;
        int16_t i16;
        int32_t i32;
        int64_t i64;
        uint8_t u8;
        uint16_t u16;
        uint32_t u32;
        uint64_t u64;
        int128_t i;
        void *p;
    };
} VALUE;

typedef struct
{
    TOKEN t;
    const char *p;
    int128_t i;
    char s[MAX_TOKEN+1];
} PARSER;

static TOKEN get_token(PARSER *parser)
{
    if (parser->t != TOKEN_ERROR)
    {
        TOKEN t = parser->t;
        parser->t = TOKEN_ERROR;
        return t;
    }

    while (isspace(parser->p[0]))
        parser->p++;

    switch (parser->p[0])
    {
        case '\0':
            parser->s[0] = '\0';
            return TOKEN_END;
        case '+': case '-': case '*': case '/':
        case '(': case ')': case '=':
            parser->s[0] = parser->p[0];
            parser->s[1] = '\0';
            parser->p++;
            return parser->s[0];
        default:
            break;
    }

    if (isalpha(parser->p[0]) || parser->p[0] == '_')
    {
        parser->s[0] = parser->p[0];
        size_t i = 1;
        for (; i < MAX_TOKEN &&
                (isalpha(parser->p[i]) || isdigit(parser->p[i]) ||
                    parser->p[i] == '_'); i++)
            parser->s[i] = parser->p[i];
        parser->s[i] = '\0';
        parser->p += i;
        return (i >= MAX_TOKEN? TOKEN_ERROR: TOKEN_NAME);
    }

    if (isdigit(parser->p[0]))
    {
        parser->s[0] = parser->p[0];
        size_t i = 1;
        for (; i < MAX_TOKEN && isdigit(parser->p[i]); i++)
            parser->s[i] = parser->p[i];
        parser->s[i] = '\0';
        parser->p += i;
        char *end = NULL;
        parser->i = (int128_t)strtoull(parser->s, &end, 10);
        if (end == NULL || *end != '\0')
            return TOKEN_ERROR;
        return (i >= MAX_TOKEN? TOKEN_ERROR: TOKEN_INTEGER);
    }

    parser->s[0] = parser->p[0];
    parser->s[1] = '\0';
    parser->p++;
    return TOKEN_ERROR;
}

static TOKEN peek_token(PARSER *parser)
{
    if (parser->t != TOKEN_ERROR)
        return parser->t;
    TOKEN t = get_token(parser);
    parser->t = t;
    return t;
}

static void unexpected_token(PARSER *parser)
{
    fprintf(stderr, "error: unexpected token \"%s\"\n", parser->s);
    abort();
}

static void expect_token(PARSER *parser, TOKEN token)
{
    TOKEN t = get_token(parser);
    if (t != token)
        unexpected_token(parser);
}

static VALUE negate(VALUE x)
{
    VALUE r;
    r.type = x.type;
    r.i    = 0x0;
    switch (r.type)
    {
        case TYPE_CHAR:
            r.c = -x.c;
            return r;
        case TYPE_INT8:
            r.i8 = -x.i8;
            return r;
        case TYPE_INT16:
            r.i16 = -x.i16;
            return r;
        case TYPE_INT32:
            r.i32 = -x.i32;
            return r;
        case TYPE_INT64:
            r.i64 = -x.i64;
            return r;
        case TYPE_UINT8:
            r.u8 = -x.u8;
            return r;
        case TYPE_UINT16:
            r.u16 = -x.u16;
            return r;
        case TYPE_UINT32:
            r.u32 = -x.u32;
            return r;
        case TYPE_UINT64:
            r.u64 = -x.u64;
            return r;
        case TYPE_INTEGER:
            r.i = -x.i;
            return r;
        default:
            if (log)
                fprintf(stderr, "error: not an integer type\n");
            r.type = TYPE_ERROR;
            return r;
    }
}

static TYPE type(VALUE x, VALUE y)
{
    if (x.type == TYPE_ERROR || y.type == TYPE_ERROR)
        return TYPE_ERROR;
    if (x.type == TYPE_UNKNOWN || y.type == TYPE_UNKNOWN)
        return TYPE_UNKNOWN;
    if (x.type == TYPE_PTR || y.type == TYPE_PTR)
    {
        if (log)
            fprintf(stderr, "error: not an integer type\n");
        return TYPE_ERROR;
    }
    return MAX(x.type, y.type);
}

static size_t size(TYPE t)
{
    switch (t)
    {
        case TYPE_BOOL: case TYPE_CHAR: case TYPE_INT8: case TYPE_UINT8:
            return sizeof(int8_t);
        case TYPE_INT16: case TYPE_UINT16:
            return sizeof(int16_t);
        case TYPE_INT32: case TYPE_UINT32:
            return sizeof(int32_t);
        case TYPE_INT64: case TYPE_UINT64:
            return sizeof(int64_t);
        case TYPE_PTR:
            return sizeof(void *);
        default:
            if (log)
                fprintf(stderr, "error: unsized type\n");
            return 0;
    }
}

static VALUE add(VALUE x, VALUE y)
{
    VALUE r;
    r.type = type(x, y);
    r.i    = 0x0;
    switch (r.type)
    {
        case TYPE_CHAR:
            r.c = x.c + y.c;
            return r;
        case TYPE_INT8:
            r.i8 = x.i8 + y.i8;
            return r;
        case TYPE_INT16:
            r.i16 = x.i16 + y.i16;
            return r;
        case TYPE_INT32:
            r.i32 = x.i32 + y.i32;
            return r;
        case TYPE_INT64:
            r.i64 = x.i64 + y.i64;
            return r;
        case TYPE_UINT8:
            r.u8 = x.u8 + y.u8;
            return r;
        case TYPE_UINT16:
            r.u16 = x.u16 + y.u16;
            return r;
        case TYPE_UINT32:
            r.u32 = x.u32 + y.u32;
            return r;
        case TYPE_UINT64:
            r.u64 = x.u64 + y.u64;
            return r;
        case TYPE_INTEGER:
            r.i = x.i + y.i;
            return r;
        default:
            if (log)
                fprintf(stderr, "error: not an integer type\n");
            r.type = TYPE_ERROR;
            return r;
    }
}

static VALUE subtract(VALUE x, VALUE y)
{
    VALUE r;
    r.type = type(x, y);
    r.i    = 0x0;
    switch (r.type)
    {
        case TYPE_CHAR:
            r.c = x.c - y.c;
            return r;
        case TYPE_INT8:
            r.i8 = x.i8 - y.i8;
            return r;
        case TYPE_INT16:
            r.i16 = x.i16 - y.i16;
            return r;
        case TYPE_INT32:
            r.i32 = x.i32 - y.i32;
            return r;
        case TYPE_INT64:
            r.i64 = x.i64 - y.i64;
            return r;
        case TYPE_UINT8:
            r.u8 = x.u8 - y.u8;
            return r;
        case TYPE_UINT16:
            r.u16 = x.u16 - y.u16;
            return r;
        case TYPE_UINT32:
            r.u32 = x.u32 - y.u32;
            return r;
        case TYPE_UINT64:
            r.u64 = x.u64 - y.u64;
            return r;
        case TYPE_INTEGER:
            r.i = x.i - y.i;
            return r;
        default:
            if (log)
                fprintf(stderr, "error: not an integer type\n");
            r.type = TYPE_ERROR;
            return r;
    }
}

static VALUE multiply(VALUE x, VALUE y)
{
    VALUE r;
    r.type = type(x, y);
    r.i    = 0x0;
    switch (r.type)
    {
        case TYPE_CHAR:
            r.c = x.c * y.c;
            return r;
        case TYPE_INT8:
            r.i8 = x.i8 * y.i8;
            return r;
        case TYPE_INT16:
            r.i16 = x.i16 * y.i16;
            return r;
        case TYPE_INT32:
            r.i32 = x.i32 * y.i32;
            return r;
        case TYPE_INT64:
            r.i64 = x.i64 * y.i64;
            return r;
        case TYPE_UINT8:
            r.u8 = x.u8 * y.u8;
            return r;
        case TYPE_UINT16:
            r.u16 = x.u16 * y.u16;
            return r;
        case TYPE_UINT32:
            r.u32 = x.u32 * y.u32;
            return r;
        case TYPE_UINT64:
            r.u64 = x.u64 * y.u64;
            return r;
        case TYPE_INTEGER:
            r.i = x.i * y.i;
            return r;
        default:
            if (log)
                fprintf(stderr, "error: not an integer type\n");
            r.type = TYPE_ERROR;
            return r;
    }
}

static VALUE evaluate(CONTEXT *ctx, PARSER *parser, bool prec);
static VALUE get_value(CONTEXT *ctx, PARSER *parser)
{
    VALUE val;
    switch (get_token(parser))
    {
        case '-':
            val = get_value(ctx, parser);
            val = negate(val);
            return val;
        case '(':
            val = evaluate(ctx, parser, false);
            expect_token(parser, ')');
            return val;
        case TOKEN_INTEGER:
            val.type = TYPE_INTEGER;
            val.i = parser->i;
            return val;
        case TOKEN_NAME:
        {
            VAR *var = ctx->vars;
            while (var != NULL && strcmp(var->name, parser->s) != 0)
                var = var->next;
            if (var == NULL)
            {
                if (log)
                    fprintf(stderr, "error: variable \"%s\" not found\n",
                        parser->s);
                val.i = 0x0;
                val.type = TYPE_ERROR;
                return val;
            }
            val.i = 0x0;
            memcpy(&val.i, var->ptr, size(var->type));
            val.type = var->type;
            return val;
        }
        default:
            unexpected_token(parser);
    }
}

static VALUE evaluate(CONTEXT *ctx, PARSER *parser, bool prec)
{
    if (prec)
        return get_value(ctx, parser);
    VALUE val = evaluate(ctx, parser, true);
    while (true)
    {
        VALUE arg;
        switch (peek_token(parser))
        {
            case '*':
                get_token(parser);
                arg = get_value(ctx, parser);
                val = multiply(val, arg);
                break;
            case '+':
                get_token(parser);
                arg = evaluate(ctx, parser, true);
                val = add(val, arg);
                break;
            case '-':
                get_token(parser);
                arg = evaluate(ctx, parser, true);
                val = subtract(val, arg);
                break;
            default:
                return val;
        }
    }
}

/****************************************************************************/
/* DWARF HANDLING:                                                          */
/****************************************************************************/

#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>

#include <dwarf.h>
#include <elfutils/libdw.h>

struct dwarf_stack_s
{
    uintptr_t data[20];
    size_t pos;
};
typedef struct dwarf_stack_s *dwarf_stack_t;

/*
 * Push a value onto the stack.
 */
static void dwarf_push_int(dwarf_stack_t stack, intptr_t val)
{
    assert(stack->pos < sizeof(stack->data) / sizeof(stack->data[0]));
    stack->data[stack->pos++] = (uintptr_t)val;
}
static void dwarf_push_uint(dwarf_stack_t stack, uintptr_t val)
{
    assert(stack->pos < sizeof(stack->data) / sizeof(stack->data[0]));
    stack->data[stack->pos++] = val;
}
static void dwarf_push_addr(dwarf_stack_t stack, uint8_t *val)
{
    assert(stack->pos < sizeof(stack->data) / sizeof(stack->data[0]));
    stack->data[stack->pos++] = (uintptr_t)val;
}

/*
 * Pop a value from the stack.
 */
static intptr_t dwarf_pop_int(dwarf_stack_t stack)
{
    assert(stack->pos > 0);
    stack->pos--;
    return (intptr_t)stack->data[stack->pos];
}
static uintptr_t dwarf_pop_uint(dwarf_stack_t stack)
{
    assert(stack->pos > 0);
    stack->pos--;
    return stack->data[stack->pos];
}
static uint8_t *dwarf_pop_addr(dwarf_stack_t stack)
{
    assert(stack->pos > 0);
    stack->pos--;
    return (uint8_t *)stack->data[stack->pos];
}

/*
 * Pick a value from the stack.
 */
static uintptr_t dwarf_pick_uint(dwarf_stack_t stack, size_t idx)
{
    assert(idx < stack->pos);
    return stack->data[stack->pos - idx];
}

/*
 * Load an integer from a register.
 */
static const void *dwarf_load_reg(const STATE *state, size_t reg)
{
	switch (reg)
    {
        case 0:  return &state->rax;
        case 1:  return &state->rdx;
        case 2:  return &state->rcx;
        case 3:  return &state->rbx;
        case 4:  return &state->rsi;
        case 5:  return &state->rdi;
        case 6:  return &state->rbp;
        case 7:  return &state->rsp;
        case 8:  return &state->r8;
        case 9:  return &state->r9;
        case 10: return &state->r10;
        case 11: return &state->r11;
        case 12: return &state->r12;
        case 13: return &state->r13;
        case 14: return &state->r14;
        case 15: return &state->r15;
		case 16: return &state->rip;
        default:
            fprintf(stderr, "error: unsupported register (%zu)\n", reg);
            abort();
    }
}
static uintptr_t dwarf_load_value(const STATE *state, size_t reg)
{
    return *(uintptr_t *)dwarf_load_reg(state, reg);
}
static intptr_t dwarf_load_int(const STATE *state, size_t reg)
{
    return (intptr_t)dwarf_load_value(state, reg);
}
static uintptr_t dwarf_load_uint(const STATE *state, size_t reg)
{
    return dwarf_load_value(state, reg);
}
static uint8_t *dwarf_load_addr(const STATE *state, size_t reg)
{
    return (uint8_t *)dwarf_load_value(state, reg);
}

static uintptr_t dwarf_evaluate(Dwarf_Op *expr, size_t expr_size,
    Dwarf_Op *cfa, size_t cfa_size, const void *base, const STATE *state)
{
    struct dwarf_stack_s stack_object;
    dwarf_stack_t stack = &stack_object;
    stack->pos = 0;

    uint8_t *a0, *a1;
    uintptr_t u0, u1, u2;
    intptr_t  s0, s1;

    const Dwarf_Op *start = expr;
    const Dwarf_Op *end   = expr + expr_size;

    while (expr < end)
    {
        Dwarf_Op *op = expr++;
        switch (op->atom)
        {
            case DW_OP_addr:
                dwarf_push_addr(stack,
                    (uint8_t *)((intptr_t)base + op->number));
                break;
            case DW_OP_reg0: case DW_OP_reg1: case DW_OP_reg2:
            case DW_OP_reg3: case DW_OP_reg4: case DW_OP_reg5:
            case DW_OP_reg6: case DW_OP_reg7: case DW_OP_reg8:
            case DW_OP_reg9: case DW_OP_reg10: case DW_OP_reg11:
            case DW_OP_reg12: case DW_OP_reg13: case DW_OP_reg14:
            case DW_OP_reg15: case DW_OP_reg16: case DW_OP_reg17:
            case DW_OP_reg18: case DW_OP_reg19: case DW_OP_reg20:
            case DW_OP_reg21: case DW_OP_reg22: case DW_OP_reg23:
            case DW_OP_reg24: case DW_OP_reg25: case DW_OP_reg26:
            case DW_OP_reg27: case DW_OP_reg28: case DW_OP_reg29:
            case DW_OP_reg30: case DW_OP_reg31:
                a0 = (uint8_t *)dwarf_load_reg(state, op->atom - DW_OP_reg0);
                dwarf_push_addr(stack, a0);
                break;
            case DW_OP_breg0: case DW_OP_breg1: case DW_OP_breg2:
            case DW_OP_breg3: case DW_OP_breg4: case DW_OP_breg5:
            case DW_OP_breg6: case DW_OP_breg7: case DW_OP_breg8:
            case DW_OP_breg9: case DW_OP_breg10: case DW_OP_breg11:
            case DW_OP_breg12: case DW_OP_breg13: case DW_OP_breg14:
            case DW_OP_breg15: case DW_OP_breg16: case DW_OP_breg17:
            case DW_OP_breg18: case DW_OP_breg19: case DW_OP_breg20:
            case DW_OP_breg21: case DW_OP_breg22: case DW_OP_breg23:
            case DW_OP_breg24: case DW_OP_breg25: case DW_OP_breg26:
            case DW_OP_breg27: case DW_OP_breg28: case DW_OP_breg29:
            case DW_OP_breg30: case DW_OP_breg31:
                a0 = dwarf_load_addr(state, op->atom - DW_OP_breg0);
                s0 = (intptr_t)op->number;
                dwarf_push_addr(stack, a0 + s0);
                break;
            case DW_OP_bregx:
                u0 = (uintptr_t)op->number;
                a0 = dwarf_load_addr(state, u0);
                s0 = (intptr_t)op->number2;
                dwarf_push_addr(stack, a0 + s0);
                break;
            case DW_OP_fbreg:
                a0 = (void *)dwarf_evaluate(cfa, cfa_size, NULL, 0, base,
                    state);
                s0 = (intptr_t)op->number;
                dwarf_push_addr(stack, a0 + s0);
                break;
            case DW_OP_plus_uconst:
                u0 = dwarf_pop_uint(stack);
                u1 = (uintptr_t)op->number;
                dwarf_push_uint(stack, u0 + u1);
                break;
            case DW_OP_deref:
                a0 = dwarf_pop_addr(stack);
                memcpy(&u0, a0, sizeof(u0));
                dwarf_push_uint(stack, u0);
                break;
            case DW_OP_deref_size:
                a0 = dwarf_pop_addr(stack);
                u0 = (uintptr_t)op->number;
                switch (u0)
                {
                    case sizeof(int8_t): case sizeof(int16_t):
                    case sizeof(int32_t): case sizeof(int64_t):
                        memcpy(&u0, a0, u0);
                        break;
                    default:
                        assert(0);
                }
                dwarf_push_uint(stack, u0);
                break;
            case DW_OP_lit0: case DW_OP_lit1: case DW_OP_lit2:
            case DW_OP_lit3: case DW_OP_lit4: case DW_OP_lit5:
            case DW_OP_lit6: case DW_OP_lit7: case DW_OP_lit8:
            case DW_OP_lit9: case DW_OP_lit10: case DW_OP_lit11:
            case DW_OP_lit12: case DW_OP_lit13: case DW_OP_lit14:
            case DW_OP_lit15: case DW_OP_lit16: case DW_OP_lit17:
            case DW_OP_lit18: case DW_OP_lit19: case DW_OP_lit20:
            case DW_OP_lit21: case DW_OP_lit22: case DW_OP_lit23:
            case DW_OP_lit24: case DW_OP_lit25: case DW_OP_lit26:
            case DW_OP_lit27: case DW_OP_lit28: case DW_OP_lit29:
            case DW_OP_lit30: case DW_OP_lit31:
                dwarf_push_uint(stack, op->atom - DW_OP_lit0);
                break;
            case DW_OP_const1u:
                u0 = (uintptr_t)op->number;
                dwarf_push_uint(stack, u0);
                break;
            case DW_OP_const2u:
                u0 = (uintptr_t)op->number;
                dwarf_push_uint(stack, u0);
                break;
            case DW_OP_const4u:
                u0 = (uintptr_t)op->number;
                dwarf_push_uint(stack, u0);
                break;
            case DW_OP_const8u:
                u0 = (uintptr_t)op->number;
                dwarf_push_uint(stack, u0);
                break;
            case DW_OP_constu:
                u0 = (uintptr_t)op->number;
                dwarf_push_uint(stack, u0);
                break;
            case DW_OP_const1s:
                s0 = (intptr_t)op->number;
                dwarf_push_int(stack, s0);
                break;
            case DW_OP_const2s:
                s0 = (intptr_t)op->number;
                dwarf_push_int(stack, s0);
                break;
            case DW_OP_const4s:
                s0 = (intptr_t)op->number;
                dwarf_push_int(stack, s0);
                break;
            case DW_OP_const8s:
                s0 = (intptr_t)op->number;
                dwarf_push_int(stack, s0);
                break;
            case DW_OP_consts:
                s0 = (intptr_t)op->number;
                dwarf_push_int(stack, s0);
                break;
            case DW_OP_dup:
                u0 = dwarf_pop_uint(stack);
                dwarf_push_uint(stack, u0);
                dwarf_push_uint(stack, u0);
                break;
            case DW_OP_drop:
                (void)dwarf_pop_uint(stack);
                break;
            case DW_OP_over:
                u0 = dwarf_pick_uint(stack, 1);
                dwarf_push_uint(stack, u0);
                break;
            case DW_OP_pick:
                u0 = (uintptr_t)op->number;
                u0 = dwarf_pick_uint(stack, u0);
                dwarf_push_uint(stack, u0);
                break;
            case DW_OP_swap:
                u0 = dwarf_pop_uint(stack);
                u1 = dwarf_pop_uint(stack);
                dwarf_push_uint(stack, u0);
                dwarf_push_uint(stack, u1);
                break;
            case DW_OP_rot:
                u0 = dwarf_pop_uint(stack);
                u1 = dwarf_pop_uint(stack);
                u2 = dwarf_pop_uint(stack);
                dwarf_push_uint(stack, u1);
                dwarf_push_uint(stack, u0);
                dwarf_push_uint(stack, u2);
                break;
            case DW_OP_abs:
                s0 = dwarf_pop_int(stack);
                s0 = (s0 < 0? -s0: s0);
                dwarf_push_int(stack, s0);
                break;
            case DW_OP_div:
                s0 = dwarf_pop_int(stack);
                assert(s0 != 0);
                s1 = dwarf_pop_int(stack);
                dwarf_push_int(stack, s1 / s0);
                break;
            case DW_OP_mod:
                s0 = dwarf_pop_int(stack);
                assert(s0 != 0);
                s1 = dwarf_pop_int(stack);
                dwarf_push_int(stack, s1 % s0);
                break;
#define DWARF_BINARY_OP(name, op, s)                                        \
                DW_OP_##name:                                               \
                s##0 = dwarf_pop_int(stack);                                \
                s##1 = dwarf_pop_int(stack);                                \
                dwarf_push_uint(stack, (uintptr_t)(s##1 op s##0));          \
                break
#define DWARF_UNARY_OP(name, op, s)                                         \
                DW_OP_##name:                                               \
                s##0 = dwarf_pop_int(stack);                                \
                dwarf_push_uint(stack, (uintptr_t)(op s##0));               \
                break
            case DWARF_BINARY_OP(shl, <<, u);
            case DWARF_BINARY_OP(shr, >>, u);
            case DWARF_BINARY_OP(shra, >>, s);
            case DWARF_BINARY_OP(and, &, u);
            case DWARF_BINARY_OP(or, |, u);
            case DWARF_BINARY_OP(xor, ^, u);
            case DWARF_UNARY_OP(not, ~, u);
            case DWARF_UNARY_OP(neg, -, s);
            case DWARF_BINARY_OP(plus, +, s);
            case DWARF_BINARY_OP(minus, -, s);
            case DWARF_BINARY_OP(mul, *, s);
            case DWARF_BINARY_OP(lt, <, s);
            case DWARF_BINARY_OP(le, <=, s);
            case DWARF_BINARY_OP(gt, >, s);
            case DWARF_BINARY_OP(ge, >=, s);
            case DWARF_BINARY_OP(eq, ==, s);
            case DWARF_BINARY_OP(ne, !=, s);
#if 0
            case DW_OP_skip:
                s0 = (intptr_t)op->number;
                expr += s0;
                break;
            case DW_OP_bra:
                s0 = dwarf_read_int16(&expr);
                u0 = dwarf_pop_uint(stack);
                if (u0 != 0)
                    expr += s0;
                break;
#endif
            case DW_OP_nop:
                break;
            case DW_OP_implicit_value:
                u0 = (uintptr_t)op->number2;
                assert(expr == end);
                return u0;
            case DW_OP_stack_value:
                u0 = dwarf_pop_uint(stack);
                assert(expr == end);
                return u0;
            default:
                fprintf(stderr, "error: unknown op code (0x%.2X)\n", op->atom);
                assert(0);
        }
    }

    u0 = dwarf_pop_uint(stack);
    return u0;
}

static void dwarf_print_type(FILE *stream, Dwarf_Die *type)
{
    if (type == NULL)
    {
        fprintf(stream, "???");
        return;
    }
    Dwarf_Attribute attr_obj, *attr;
    Dwarf_Die type_obj;
    switch (dwarf_tag(type))
    {
        case DW_TAG_base_type:
            fprintf(stream, "%s", dwarf_diename(type));
            return;
        case DW_TAG_pointer_type:
            attr = dwarf_attr(type, DW_AT_type, &attr_obj);
            type = dwarf_formref_die(attr, &type_obj);
            dwarf_print_type(stream, type);
            fprintf(stream, " *");
            return;
        case DW_TAG_array_type:
        {
            Dwarf_Die child_obj, *child = &child_obj;
            if (!dwarf_haschildren(type) || dwarf_child(type, child) != 0)
                goto unknown;
            attr = dwarf_attr(child, DW_AT_upper_bound, &attr_obj);
            Dwarf_Word n;
            dwarf_formudata(attr, &n);
            attr = dwarf_attr(type, DW_AT_type, &attr_obj);
            type = dwarf_formref_die(attr, &type_obj);
            dwarf_print_type(stream, type);
            fprintf(stream, "[%lu]", n+1);
            return;
        }
        unknown:
        default:
            fprintf(stream, "???");
            return;
    }
}

static void dwarf_print_value(FILE *stream, Dwarf_Die *type, void *ptr)
{
    if (type == NULL)
    {
        fprintf(stream, "???");
        return;
    }
    Dwarf_Attribute attr_obj, *attr;
    Dwarf_Die type_obj;
    switch (dwarf_tag(type))
    {
        case DW_TAG_base_type:
        {
            attr = dwarf_attr(type, DW_AT_byte_size, &attr_obj);
            Dwarf_Word size = 0;
            dwarf_formudata(attr, &size);
            attr = dwarf_attr(type, DW_AT_encoding, &attr_obj);
            Dwarf_Word encoding = 0;
            dwarf_formudata(attr, &encoding);
            switch (encoding)
            {
                case DW_ATE_signed:
                    switch (size)
                    {
                        case sizeof(int8_t):
                            fprintf(stream, "%d", *(int8_t *)ptr);
                            return;
                        case sizeof(int16_t):
                            fprintf(stream, "%d", *(int16_t *)ptr);
                            return;
                        case sizeof(int32_t):
                            fprintf(stream, "%d", *(int32_t *)ptr);
                            return;
                        case sizeof(int64_t):
                            fprintf(stream, "%ld", *(int64_t *)ptr);
                            return;
                        default:
                            fprintf(stream, "???");
                            return;
                    }
                    break;
                case DW_ATE_unsigned:
                    switch (size)
                    {
                        case sizeof(uint8_t):
                            fprintf(stream, "%u", *(uint8_t *)ptr);
                            return;
                        case sizeof(uint16_t):
                            fprintf(stream, "%u", *(uint16_t *)ptr);
                            return;
                        case sizeof(uint32_t):
                            fprintf(stream, "%u", *(uint32_t *)ptr);
                            return;
                        case sizeof(uint64_t):
                            fprintf(stream, "%lu", *(uint64_t *)ptr);
                            return;
                        default:
                            fprintf(stream, "???");
                            return;
                    }
                case DW_ATE_signed_char: case DW_ATE_unsigned_char:
                    switch (size)
                    {
                        case sizeof(char):
                            fprintf(stream, "\'%c\'", *(char *)ptr);
                            return;
                        case sizeof(wchar_t):
                            fprintf(stream, "\'%lc\'", *(wchar_t *)ptr);
                            return;
                        default:
                            fprintf(stream, "???");
                            return;
                    }
                case DW_ATE_boolean:
                    switch (size)
                    {
                        case sizeof(bool):
                            fprintf(stream, "%s",
                                (*(bool *)ptr? "true": "false"));
                            return;
                        default:
                            fprintf(stream, "???");
                            return;
                    }
                case DW_ATE_float:
                    switch (size)
                    {
                        case sizeof(float):
                            fprintf(stream, "%ff", (double)*(float *)ptr);
                            return;
                        case sizeof(double):
                            fprintf(stream, "%f", *(double *)ptr);
                            return;
                    }
                default:
                    fprintf(stream, "???");
                    return;
            }
        }
        case DW_TAG_pointer_type:
            fprintf(stream, "%p", *(void **)ptr);
            return;
        case DW_TAG_array_type:
        {
            Dwarf_Die child_obj, *child = &child_obj;
            if (!dwarf_haschildren(type) || dwarf_child(type, child) != 0)
                goto unknown;
            attr = dwarf_attr(child, DW_AT_upper_bound, &attr_obj);
            Dwarf_Word n;
            dwarf_formudata(attr, &n);
            attr = dwarf_attr(type, DW_AT_type, &attr_obj);
            type = dwarf_formref_die(attr, &type_obj);
            Dwarf_Word size;
            if (dwarf_aggregate_size(type, &size) != 0)
                goto unknown;
            uint8_t *elem = (uint8_t *)ptr;
            for (Dwarf_Word i = 0; i <= n; i++)
            {
                fputc((i == 0? '{': ','), stream);
                dwarf_print_value(stream, type, (void *)elem);
                elem += size;
            }
            fputc('}', stream);
            return;
        }

        unknown:
        default:
            fprintf(stream, "???");
            break;
    }
}

static TYPE dwarf_get_type(Dwarf_Die *type);
static VAR *dwarf_get_variable(Dwarf_Die *var, Dwarf_Op *cfa, size_t cfa_size,
    const void *base, const void *addr, STATE *state, VAR *vars);

static bool inited = false;
static Dwarf *debug = NULL;
static Dwarf_CFI *cfi = NULL;

static __attribute__((__constructor__(3333))) void dwarf_init(void)
{
    if (getenv("PATCH_DEBUG") != NULL)
        log = true;

    const char *filename = "/proc/self/exe";
    int fd = open(filename, O_RDONLY);
    if (fd < 0)
    {
        fprintf(stderr, "error: failed to open \"%s\" for reading: %s\n",
            filename, strerror(errno));
        fprintf(stderr, "       (did you forget to compile with -g?)\n");
        abort();
    }

    debug = dwarf_begin(fd, DWARF_C_READ);
    if (debug == NULL)
    {
        fprintf(stderr, "error: failed to read DWARF debug information for "
            "\"%s\": %s\n", filename, dwarf_errmsg(dwarf_errno()));
        abort();
    }

    cfi = dwarf_getcfi_elf(dwarf_getelf(debug));
    if (cfi == NULL)
    {
        fprintf(stderr, "error: failed to get the DWARF CFI information: %s\n",
            dwarf_errmsg(dwarf_errno()));
        abort();
    }
}

static VAR *dwarf_get_variables(const void *base, const void *addr,
    STATE *state)
{
    // Get frame information:
    Dwarf_Frame *frame;
    if (dwarf_cfi_addrframe(cfi, (Dwarf_Addr)addr, &frame) != 0)
    {
        if (log)
            fprintf(stderr, "warning: failed to get DWARF frame information "
                "for address %p: %s\n", addr, dwarf_errmsg(dwarf_errno()));
        return NULL;
    }

    Dwarf_Op *cfa;
    size_t cfa_size;
    if (dwarf_frame_cfa(frame, &cfa, &cfa_size) != 0)
    {
        if (log)
            fprintf(stderr, "warning: failed to get Canonical Frame Address "
                " (CFA) DWARF expression: %s\n", dwarf_errmsg(dwarf_errno()));
        return NULL;
    }

    // Scan all compilation units for the `addr':
    VAR *vars = NULL;
    Dwarf_Off offset = 0, last_offset = 0;
    size_t hdr_size; 
    while (dwarf_nextcu(debug, offset, &offset, &hdr_size, 0, 0, 0) == 0)
    {
        Dwarf_Die cudie_obj, *cudie;
        if ((cudie = dwarf_offdie(debug, last_offset + hdr_size, &cudie_obj))
                == NULL)
        {
            last_offset = offset;
            continue;
        }
        last_offset = offset;

        Dwarf_Die *scopes = NULL;
        int n = dwarf_getscopes(cudie, (Dwarf_Addr)addr, &scopes);
        if (n < 0)
            continue;

        // Scan all scopes for parameters and variables:
        for (int i = 0; i < n; i++)
        {
            Dwarf_Die *scope = scopes + i, child_obj;
            Dwarf_Die *child = &child_obj; 
            if (!dwarf_haschildren(scope) || dwarf_child(scope, child) != 0)
                continue;
            do
            {
                switch (dwarf_tag(child))
                {
                    case DW_TAG_variable:
                    case DW_TAG_formal_parameter:
                        break;
                    default:
                        continue;
                }
                vars = dwarf_get_variable(child, cfa, cfa_size, base, addr,
                    state, vars);
            }
            while (dwarf_siblingof(child, child) == 0);
        }
    }

	return vars;
}

static VAR *dwarf_get_variable(Dwarf_Die *var, Dwarf_Op *cfa, size_t cfa_size,
    const void *base, const void *addr, STATE *state, VAR *vars)
{
    if (dwarf_diename(var) == NULL)
    {
        // No name?
        return vars;
    }

    Dwarf_Attribute attr_obj;
    Dwarf_Attribute *attr = dwarf_attr(var, DW_AT_location, &attr_obj);
    if (attr == NULL)
        return vars;
    Dwarf_Op *loc = NULL;
    size_t loc_size;
    if (dwarf_getlocation_addr(attr, (Dwarf_Addr)addr, &loc, &loc_size, 1) != 1)
    {
        if (log)
            fprintf(stderr, "warning: failed to decode DW_AT_location for "
                "(%s): %s\n",
                dwarf_diename(var), dwarf_errmsg(dwarf_errno()));
        return vars;
    }

    attr = dwarf_attr(var, DW_AT_type, &attr_obj);
    if (attr == NULL)
    {
        if (log)
            fprintf(stderr, "warning: missing DW_AT_type for (%s)\n",
                dwarf_diename(var));
        return vars;
    }
    Dwarf_Die type_obj;
    Dwarf_Die *type = dwarf_formref_die(attr, &type_obj);
    if (type == NULL)
    {
        if (log)
            fprintf(stderr, "warning: failed to get type die for (%s)\n",
                dwarf_diename(var));
        return vars;
    }

    TYPE t = dwarf_get_type(type);
    if (t == TYPE_UNKNOWN)
    {
        if (log)
            fprintf(stderr, "warning: unknown type for (%s)\n",
                dwarf_diename(var));
        return vars;
    }

    VAR *entry = (VAR *)malloc(sizeof(VAR));
    assert(entry != NULL);
    entry->name = strdup(dwarf_diename(var));
    assert(entry->name != NULL);
    entry->type = t;
    entry->ptr  = (void *)dwarf_evaluate(loc, loc_size, cfa, cfa_size,
        base, state);
    assert(entry->ptr != NULL);
    entry->next = vars;
    vars = entry;

//    if (log)
//    {
//        fprintf(stderr, "\33[32m");
//        dwarf_print_type(stderr, type);
//        fprintf(stderr, "\33[0m %s = \33[31m", dwarf_diename(var));
//        dwarf_print_value(stderr, type, entry->ptr);
//        fprintf(stderr, "\33[0m\n");
//    }

    return vars;
}

static TYPE dwarf_get_type(Dwarf_Die *type)
{
    switch (dwarf_tag(type))
    {
        case DW_TAG_pointer_type:
            return TYPE_PTR;
        case DW_TAG_base_type:
        {
            Dwarf_Attribute attr_obj, *attr;
            attr = dwarf_attr(type, DW_AT_byte_size, &attr_obj);
            Dwarf_Word size = 0;
            dwarf_formudata(attr, &size);
            attr = dwarf_attr(type, DW_AT_encoding, &attr_obj);
            Dwarf_Word encoding = 0;
            dwarf_formudata(attr, &encoding);
            switch (encoding)
            {
                case DW_ATE_signed:
                    switch (size)
                    {
                        case sizeof(int8_t):
                            return TYPE_INT8;
                        case sizeof(int16_t):
                            return TYPE_INT16;
                        case sizeof(int32_t):
                            return TYPE_INT32;
                        case sizeof(int64_t):
                            return TYPE_INT64;
                        default:
                            return TYPE_UNKNOWN;
                    }
                case DW_ATE_unsigned:
                    switch (size)
                    {
                        case sizeof(uint8_t):
                            return TYPE_UINT8;
                        case sizeof(uint16_t):
                            return TYPE_UINT16;
                        case sizeof(uint32_t):
                            return TYPE_UINT32;
                        case sizeof(uint64_t):
                            return TYPE_UINT64;
                        default:
                            return TYPE_UNKNOWN;
                    }
                case DW_ATE_signed_char:
                    if (size == sizeof(char))
                        return TYPE_CHAR;
                    else
                        return TYPE_UNKNOWN;
                case DW_ATE_boolean:
                    return TYPE_BOOL;
                default:
                    return TYPE_UNKNOWN;
            }
        }
        default:
            return TYPE_UNKNOWN;
    }
}

/****************************************************************************/
/* ENTRY POINT FROM E9TOOL INSTRUMENTATION                                  */
/****************************************************************************/

void patch(const char *expr, const void *base, const void *addr, STATE *state)
{
//    if (log)
//        printf("\naddr = \33[33m%p\33[0m:\n", addr);

    VAR *vars = dwarf_get_variables(base, addr, state);
    CONTEXT ctx = {state, vars};
    PARSER parser;
    parser.p = expr;
    parser.t = TOKEN_ERROR;
    parser.s[0] = '\0';

    expect_token(&parser, TOKEN_NAME);
    VAR *lhs = vars;
    while (lhs != NULL && strcmp(lhs->name, parser.s) != 0)
        lhs = lhs->next;
    if (lhs == NULL)
    {
        if (log)
            fprintf(stderr, "error: LHS variable %s not found\n", parser.s);
        return;
    }
    expect_token(&parser, '=');

    VALUE result = evaluate(&ctx, &parser, false);
    if (get_token(&parser) != TOKEN_END)
    {
        fprintf(stderr, "error: expected end-of-input; found \"%s\"\n",
            parser.s);
        abort();
    }

    switch (result.type)
    {
        case TYPE_INT8:
            printf("%s = %d\n", expr, result.i8); break;
        case TYPE_INT16:
            printf("%s = %d\n", expr, result.i16); break;
        case TYPE_INT32:
            printf("%s = %d\n", expr, result.i32); break;
        case TYPE_INT64:
            printf("%s = %ld\n", expr, result.i64); break;
        case TYPE_UINT8:
            printf("%s = %d\n", expr, result.u8); break;
        case TYPE_UINT16:
            printf("%s = %d\n", expr, result.u16); break;
        case TYPE_UINT32:
            printf("%s = %d\n", expr, result.u32); break;
        case TYPE_UINT64:
            printf("%s = %ld\n", expr, result.u64); break;
    }

    // Do the assignment:
    memcpy(lhs->ptr, &result.i, size(lhs->type));
	
    VAR *prev = NULL;
    while (vars != NULL)
    {
        prev = vars;
        vars = vars->next;
        free((void *)prev->name);
        free(prev);
    }

}

