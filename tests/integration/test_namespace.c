/* These ordinary names belong to the embedding application. */
#include <x87trans/x87trans.h>
void decode(void) {}
void rounded(void) {}
void scale2(void) {}
void result_begin(void) {}
const int ONE = 1, ZERO = 0;
int main(void)
{
    x87t_context *context = x87t_create();
    if (!context)
        return 1;
    x87t_destroy(context);
    return 0;
}
