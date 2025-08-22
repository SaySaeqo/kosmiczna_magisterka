#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <pigpio.h>
#define CHECK_STATUS(status, msg) \
    if (status != 0) { \
        PyErr_SetString(PyExc_Exception, msg); \
        return NULL; \
    }

static PyObject* generate_signal(PyObject* self, PyObject* args)
{
    int status;
    int pin;
    int how_much;
    if (!PyArg_ParseTuple(args, "ii", &pin, &how_much))
    {
        return NULL;
    }
    

    if (gpioInitialise() < 0)
    {
        PyErr_SetString(PyExc_Exception, "Failed to initialize GPIO");
        return NULL;
    }
    status = gpioSetMode(pin, PI_OUTPUT);
    CHECK_STATUS(status, "Failed to set GPIO mode");
    for (int i = 0; i < how_much; i++)
    {
        status = gpioWrite(pin, 1);
        CHECK_STATUS(status, "Failed to write GPIO");
        status = gpioWrite(pin, 0);
        CHECK_STATUS(status, "Failed to write GPIO");
    }
    gpioTerminate();

    Py_RETURN_NONE;
}

static PyMethodDef fast_motor_funcs[] = {
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
    .m_doc = "Module for accelerating stepper motor wave generations.",
    .m_methods = fast_motor_funcs,
};

PyMODINIT_FUNC PyInit_fast_motor(void) {
	return PyModule_Create(&fast_motor_module);
}
