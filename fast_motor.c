#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <pigpio.h>
#include <stdio.h>
#include <time.h>
#include <math.h>
#define ASSERT_SUCCESS(status, msg) \
    if (status < 0) { \
        PyErr_SetString(PyExc_Exception, msg); \
        return -1; \
    }
#define SLEEP_PREP \
    struct timespec ts, rem; \
    ts.tv_sec = 0;
#define SLEEP(nanoseconds) \
    ts.tv_nsec = nanoseconds; \
    while (clock_nanosleep(CLOCK_MONOTONIC, 0, &ts, &rem)) \
    {                                                      \
        ts.tv_sec  = rem.tv_sec;                           \
        ts.tv_nsec = rem.tv_nsec;                          \
    }
#define STEP_PIN 24
#define ROTATION_PER_STEP (M_PI/1600)
#define CALCULATION_TIME_NS 260
#define WRITING_TIME_NS 1100
#define INIT_TIME_NS 6000 // 3000-80000 ns
#define CALCULATION_TIME_ALL_NS 350000
#define TIME_CALC_START \
    struct timespec start, end; \
    int elapsed; \
    clock_gettime(CLOCK_MONOTONIC, &start);

#define TIME_CALC_END \
    clock_gettime(CLOCK_MONOTONIC, &end); \
    elapsed = (end.tv_sec - start.tv_sec) * 1000000000 + (end.tv_nsec - start.tv_nsec); \

static void fast_motor_atexit(void) {
    gpioTerminate();
}

static int
fast_motor_module_exec(PyObject *m)
{
    ASSERT_SUCCESS(gpioInitialise(), "Failed to initialize PIGPIO");
    ASSERT_SUCCESS(Py_AtExit(fast_motor_atexit), "Failed to register PIGPIO exit handler");
    ASSERT_SUCCESS(gpioSetMode(STEP_PIN, PI_OUTPUT), "Failed to set GPIO mode");
    return 0;
}


static PyObject* generate_signal_prep(PyObject* self, PyObject* args)
{
    float acceleration, duration;
    int freq;
    if (!PyArg_ParseTuple(args, "fif", &acceleration, &freq, &duration))
    {
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS

    SLEEP_PREP
    float time_passed = 0.0;
    float impulse_duration = 1.0 / freq;
    float acc_const = acceleration / ROTATION_PER_STEP;

    int wait_times[20000];
    int wait_times_length = 0;

    while (time_passed < duration)
    {
        int sleep_time = (int)(impulse_duration * 500000000);
        time_passed += impulse_duration;
        impulse_duration = 1.0 / (freq + acc_const * time_passed);

        wait_times[wait_times_length++] = sleep_time;
    }
    
    for (int i = 0; i < wait_times_length; i++)
    {
        gpioWrite(STEP_PIN, 1);
        SLEEP(wait_times[i])
        gpioWrite(STEP_PIN, 0);
        SLEEP(wait_times[i])
    }

    Py_END_ALLOW_THREADS

    Py_RETURN_NONE;
}

static PyObject* generate_signal(PyObject* self, PyObject* args) // makes 2x more rotation
{
    gpioWrite(STEP_PIN, 1);

    // Init time calculation start
    struct timespec start, end;
    int init_time;
    clock_gettime(CLOCK_MONOTONIC, &start);
    // ----

    float duration, acceleration;
    int freq;
    if (!PyArg_ParseTuple(args, "fif", &acceleration, &freq, &duration))
    {
        return NULL;
    }

    SLEEP_PREP
    float time_passed = 0.0;
    float impulse_duration = 1.0 / freq;
    float acc_const = acceleration / ROTATION_PER_STEP;

    // Init time calculation end
    clock_gettime(CLOCK_MONOTONIC, &end);
    init_time = (end.tv_sec - start.tv_sec) * 1000000000 + (end.tv_nsec - start.tv_nsec);
    // ----

    int sleep_time = (int)(impulse_duration * 500000000);
    time_passed += impulse_duration;
    impulse_duration = 1.0 / (freq + acc_const * time_passed);
    SLEEP(sleep_time-WRITING_TIME_NS-CALCULATION_TIME_NS-init_time)
    gpioWrite(STEP_PIN, 0);

    while (time_passed < duration)
    {
        SLEEP(sleep_time-WRITING_TIME_NS-CALCULATION_TIME_NS)
        sleep_time = (int)(impulse_duration * 500000000);
        time_passed += impulse_duration;
        impulse_duration = 1.0 / (freq + acc_const * time_passed);
        gpioWrite(STEP_PIN, 1);
        SLEEP(sleep_time-WRITING_TIME_NS)
        gpioWrite(STEP_PIN, 0);
    }

    Py_RETURN_NONE;
}

static PyMethodDef fast_motor_funcs[] = {
    {	
        "generate_signal_prep",
		generate_signal_prep,
		METH_VARARGS,
		"Generates a wave signal for given parameters. (simple version)"
    },
    {	
        "generate_signal",
		generate_signal,
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
