#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <pigpio.h>
#include <stdio.h>
#define ASSERT_SUCCESS(status, msg) \
    if (status < 0) { \
        PyErr_SetString(PyExc_Exception, msg); \
        return -1; \
    }
    
static void fast_motor_atexit(void) {
    gpioTerminate();
}

static int
fast_motor_module_exec(PyObject *m)
{
    ASSERT_SUCCESS(gpioInitialise(), "Failed to initialize PIGPIO");
    ASSERT_SUCCESS(Py_AtExit(fast_motor_atexit), "Failed to register PIGPIO exit handler");
    return 0;
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
    acc_const *= 2; // acc for rot2 = acc * inertia_ratio * angle / (dur/2)^2 but acc for rot1 = 2 * acc * inertia_ratio * angle / dur^2
    duration /= 2;

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

    acc_const = -acc_const;
    time_passed = 0.0;
    freq = 1.0 / impulse_duration;

    useconds_t nwait_times[20000];
    int nwait_times_length = 0;

    while (time_passed < duration)
    {
        useconds_t sleep_time = (useconds_t)(impulse_duration * 500000);
        time_passed += impulse_duration;
        impulse_duration = 1.0 / (freq + acc_const * time_passed);

        nwait_times[nwait_times_length++] = sleep_time;
    }

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
        // printf("Impulse duration: %d microseconds\n", sleep_time * 2);
    }
    for (int i = 0; i < nwait_times_length; i++)
    {
        // start_loop = gpioTick();
        gpioWrite(pin, 1);
        gpioSleep(PI_TIME_RELATIVE, 0, nwait_times[i]);
        gpioWrite(pin, 0);
        gpioSleep(PI_TIME_RELATIVE, 0, nwait_times[i]);
        // end_loop = gpioTick();
        // printf("Loop duration: %d microseconds\n", end_loop - start_loop);
        // printf("Impulse duration: %d microseconds\n", sleep_time * 2);
    }
    Py_END_ALLOW_THREADS

    printf("Max freq: %f\tLast freq: %f\n", 1.0/wait_times[wait_times_length-1]*500000.0, 1.0/nwait_times[nwait_times_length-1]*500000.0);
    Py_RETURN_NONE;
}

static PyObject* generate_signal2(PyObject* self, PyObject* args)
{
    int calculations_start = gpioTick();
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

    int calculations_time = gpioTick() - calculations_start;

    Py_BEGIN_ALLOW_THREADS
    for (int i = 0; i < wait_times_length; i++)
    {
        // start_loop = gpioTick();
        gpioWrite(pin, 1);
        gpioDelay(wait_times[i]);
        gpioWrite(pin, 0);
        gpioDelay(wait_times[i]);
        // end_loop = gpioTick();
        // printf("Loop duration: %d microseconds\n", end_loop - start_loop);
        // printf("Impulse duration: %d microseconds\n", sleep_time * 2);
    }
    Py_END_ALLOW_THREADS

    printf("Max freq: %f\tLast wait time: %d\n", 1.0/wait_times[wait_times_length-1]*500000.0, wait_times[wait_times_length-1]);
    Py_RETURN_NONE;
}

static PyObject* generate_signal3(PyObject* self, PyObject* args)
{
    int init_start = gpioTick();
    int pin;
    float acc_const, duration;
    int freq;
    if (!PyArg_ParseTuple(args, "ifif", &pin, &acc_const, &freq, &duration))
    {
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS

    float time_passed = 0.0;
    float impulse_duration = 1.0 / freq;

    int calculations_start = gpioTick();
    useconds_t sleep_time = (useconds_t)(impulse_duration * 500000);
    time_passed += impulse_duration;
    impulse_duration = 1.0 / (freq + acc_const * time_passed);
    useconds_t calculations_time = (useconds_t)(gpioTick() - calculations_start);

    while (time_passed < duration + impulse_duration)
    {
        gpioWrite(pin, 1);
        gpioDelay(sleep_time - calculations_time);
        gpioWrite(pin, 0);
        gpioDelay(sleep_time);
        sleep_time = (useconds_t)(impulse_duration * 500000);
        time_passed += impulse_duration;
        impulse_duration = 1.0 / (freq + acc_const * time_passed);
    }
    Py_END_ALLOW_THREADS

    printf("Calculations time: %d us\tInit time: %d us\tLast impulse duration: %d us\n", calculations_time, calculations_start - init_start, sleep_time*2);

    Py_RETURN_NONE;
}

static PyMethodDef fast_motor_funcs[] = {
    {	
        "generate_signal",
		generate_signal,
		METH_VARARGS,
		"Generates a wave signal for given parameters."
    },
    {	
        "generate_signal2",
		generate_signal2,
		METH_VARARGS,
		"Generates a wave signal for given parameters. (simple version)"
    },
    {	
        "generate_signal3",
		generate_signal3,
		METH_VARARGS,
		"Generates a wave signal for given parameters. (adhoc calc version)"
    },
	{NULL, NULL, 0, NULL} // Sentinel
};

static PyModuleDef_Slot fast_motor_module_slots[] = {
    {Py_mod_exec, fast_motor_module_exec},
    {0, NULL}
};

static struct PyModuleDef fast_motor_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "fast_motor",
    .m_size = 0, // allow module re-initialization
    .m_doc = "Module for accelerating stepper motor wave generations.",
    .m_methods = fast_motor_funcs,
    .m_slots = fast_motor_module_slots,
};

PyMODINIT_FUNC PyInit_fast_motor(void) {
    return PyModuleDef_Init(&fast_motor_module);
}
