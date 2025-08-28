#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <pigpio.h>
#include <stdio.h>
#define ASSERT_SUCCESS(status, msg) \
    if (status < 0) { \
        PyErr_SetString(PyExc_Exception, msg); \
        return NULL; \
    }

static PyObject* test_signal(PyObject* self, PyObject* args)
{
    int pin;
    int how_much;
    if (!PyArg_ParseTuple(args, "ii", &pin, &how_much))
    {
        return NULL;
    }
    
    ASSERT_SUCCESS(gpioInitialise(), "Failed to initialize GPIO");
    ASSERT_SUCCESS(gpioSetMode(pin, PI_OUTPUT), "Failed to set GPIO mode");
    for (int i = 0; i < how_much; i++)
    {
        ASSERT_SUCCESS(gpioWrite(pin, 1), "Failed to write GPIO");
        ASSERT_SUCCESS(gpioWrite(pin, 0), "Failed to write GPIO");
    }
    gpioTerminate();

    Py_RETURN_NONE;
}

static PyObject* generate_signal(PyObject* self, PyObject* args)
{
    int pin;
    float acc_const, duration;
    int freq;
    if (!PyArg_ParseTuple(args, "ifif", &pin, &acc_const, &freq, &duration))
    {
        return NULL;
    }

    float time_passed = 0.0;
    float impulse_duration = 1.0 / freq;

    useconds_t wait_times[20000];
    int wait_times_length = 0;

    while (time_passed < duration)
    {
        useconds_t sleep_time = (useconds_t)(impulse_duration * 500000);
        time_passed += impulse_duration;
        impulse_duration = 1.0 / (freq + acc_const * time_passed);

        wait_times[wait_times_length++] = sleep_time;
    }

    ASSERT_SUCCESS(gpioInitialise(), "Failed to initialize GPIO");
    ASSERT_SUCCESS(gpioSetMode(pin, PI_OUTPUT), "Failed to set GPIO mode");

    int start_loop, end_loop;

    Py_BEGIN_ALLOW_THREADS
    for (int i = 0; i < wait_times_length; i++)
    {
        // start_loop = gpioTick();
        gpioWrite(pin, 1);
        gpioSleep(PI_TIME_RELATIVE, 0, wait_times[i]);
        gpioWrite(pin, 0);
        gpioSleep(PI_TIME_RELATIVE, 0, wait_times[i]);
        // end_loop = gpioTick();
        // printf("Loop duration: %d microseconds\n", end_loop - start_loop);
        // printf("Impulse duration: %f microseconds\n", sleep_time * 2);
    }
    Py_END_ALLOW_THREADS
    
    gpioTerminate();

    Py_RETURN_NONE;
}

static PyMethodDef fast_motor_funcs[] = {
	{	
        "test_signal",
		test_signal,
		METH_VARARGS,
		"Generates a wave signal for given parameters."
    },
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
