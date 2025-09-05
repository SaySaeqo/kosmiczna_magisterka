#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <pigpio.h>
#include <stdio.h>
#include <time.h>
#include <math.h>
#include <stdbool.h>
#define ASSERT_SUCCESS(status, msg) \
    if (status < 0) { \
        PyErr_SetString(PyExc_Exception, msg); \
        return -1; \
    }
#define ASSERT_SUCCESS_NULL(status, msg) \
    if (status < 0) { \
        PyErr_SetString(PyExc_Exception, msg); \
        return NULL; \
    }
#define SLEEP_PREP \
    struct timespec ts, rem; \
    ts.tv_sec = 0;
#define SLEEP(nanoseconds) \
    ts.tv_nsec = nanoseconds; \
    while (clock_nanosleep(CLOCK_MONOTONIC, 0, &ts, &rem) == EINTR) \
    {                                                      \
        ts.tv_sec  = rem.tv_sec;                           \
        ts.tv_nsec = rem.tv_nsec;                          \
    }
#define STEP_PIN 24
#define M1_PIN 17
#define M2_PIN 27
#define M3_PIN 22
#define DIR_PIN 23
#define ENABLE_PIN 4
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
    ASSERT_SUCCESS(gpioSetMode(ENABLE_PIN, PI_OUTPUT), "Failed to set GPIO mode");
    ASSERT_SUCCESS(gpioSetMode(DIR_PIN, PI_OUTPUT), "Failed to set GPIO mode");
    ASSERT_SUCCESS(gpioSetMode(M1_PIN, PI_OUTPUT), "Failed to set GPIO mode");
    ASSERT_SUCCESS(gpioSetMode(M2_PIN, PI_OUTPUT), "Failed to set GPIO mode");
    ASSERT_SUCCESS(gpioSetMode(M3_PIN, PI_OUTPUT), "Failed to set GPIO mode");
    return 0;
}

static PyObject* setup_motor(PyObject* self)
{
    ASSERT_SUCCESS_NULL(gpioWrite(M1_PIN, 1), "Failed to write to GPIO");
    ASSERT_SUCCESS_NULL(gpioWrite(M2_PIN, 1), "Failed to write to GPIO");
    ASSERT_SUCCESS_NULL(gpioWrite(M3_PIN, 1), "Failed to write to GPIO");
    ASSERT_SUCCESS_NULL(gpioWrite(STEP_PIN, 0), "Failed to write to GPIO");
    ASSERT_SUCCESS_NULL(gpioWrite(DIR_PIN, 0), "Failed to write to GPIO");
    ASSERT_SUCCESS_NULL(gpioWrite(ENABLE_PIN, 0), "Failed to write to GPIO");
    Py_RETURN_NONE;
}

static PyObject* cleanup_motor(PyObject* self)
{
    ASSERT_SUCCESS_NULL(gpioWrite(ENABLE_PIN, 1), "Failed to write to GPIO");
    Py_RETURN_NONE;
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
    float freq;
    if (!PyArg_ParseTuple(args, "fff", &acceleration, &freq, &duration))
    {
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS
    SLEEP_PREP
    if (freq > 0.0) {
        gpioWrite(DIR_PIN, 0);
    } else {
        gpioWrite(DIR_PIN, 1);
        freq = -freq;
        acceleration = -acceleration;
    }
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
    Py_END_ALLOW_THREADS

    printf("Signal generation finished\n");
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
    {	
        "setup",
        setup_motor,
        METH_NOARGS,
        "Sets up the motor by configuring GPIO pins."
    },
    {    
        "cleanup",
        cleanup_motor,
        METH_NOARGS,
        "Cleans up the motor by resetting GPIO pins."
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
