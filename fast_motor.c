#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <pigpio.h>


static PyObject* generate_signal(PyObject* self, PyObject* args)
{
    int pin;
    int how_much;
    if (!PyArg_ParseTuple(args, "ii", &pin, &how_much))
    {
        return NULL;
    }
    

    gpioInitialise();
    gpioSetMode(pin, PI_OUTPUT);
    for (int i = 0; i < how_much; i++)
    {
        gpioWrite(pin, 1);
        gpioWrite(pin, 0);
    }
    gpioTerminate();
    
    Py_RETURN_NONE;
}

PyMODINIT_FUNC
PyInit_fast_motor(void)
{
    return PyModuleDef_Init(&fast_motor_module);
}

char fast_motor_func_docs[] = ;

PyMethodDef fast_motor_funcs[] = {
	{	
        "generate_signal",
		generate_signal,
		METH_VARARGS,
		"Generates a wave signal for given parameters."
    },
	{NULL, NULL, 0, NULL} // Sentinel
};

static struct PyModuleDef fast_motor_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "fast_motor",
    .m_size = 0, // allow module re-initialization
    .m_doc = "Module for accelerating stepper motor wave generations."
    .m_methods = fast_motor_funcs,
};

PyMODINIT_FUNC PyInit_fast_motor(void) {
	return PyModule_Create(&fast_motor_module);
}