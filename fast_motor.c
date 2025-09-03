#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <pigpio.h>
#include <stdio.h>
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


static void fast_motor_atexit(void) {
    gpioTerminate();
}

static int
fast_motor_module_exec(PyObject *m)
{
    ASSERT_SUCCESS(gpioInitialise(), "Failed to initialize PIGPIO");
    ASSERT_SUCCESS(Py_AtExit(fast_motor_atexit), "Failed to register PIGPIO exit handler");
    ASSERT_SUCCESS(gpioSetMode(24, PI_OUTPUT), "Failed to set GPIO mode");
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
    struct timespec calculations_start, calculations_end;
    int pin;
    float acc_const, duration;
    int freq;
    if (!PyArg_ParseTuple(args, "ifif", &pin, &acc_const, &freq, &duration))
    {
        return NULL;
    }

    clock_gettime(CLOCK_MONOTONIC, &calculations_start);
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
    clock_gettime(CLOCK_MONOTONIC, &calculations_end);
    int calculations_time = (calculations_end.tv_sec - calculations_start.tv_sec) * 1000000000 +
                            (calculations_end.tv_nsec - calculations_start.tv_nsec);

    struct timespec write_start, write_end;
    clock_gettime(CLOCK_MONOTONIC, &write_start);
    gpioWrite(pin, 1);
    gpioWrite(pin, 0);
    clock_gettime(CLOCK_MONOTONIC, &write_end);
    int write_time = (write_end.tv_sec - write_start.tv_sec) * 1000000000 +
                     (write_end.tv_nsec - write_start.tv_nsec);

    Py_BEGIN_ALLOW_THREADS
    for (int i = 0; i < wait_times_length; i++)
    {
        gpioWrite(pin, 1);
        gpioSleep(PI_TIME_RELATIVE, 0, wait_times[i]);
        gpioWrite(pin, 0);
        gpioSleep(PI_TIME_RELATIVE, 0, wait_times[i]);
    }
    Py_END_ALLOW_THREADS

    printf("Max freq: %f\tLast wait time: %d\tWriting time: %d ns\tCalculations time: %d ns\n", 1.0/wait_times[wait_times_length-1]*500000.0, wait_times[wait_times_length-1], write_time, calculations_time);
    Py_RETURN_NONE;
}

static PyObject* generate_signal3(PyObject* self, PyObject* args) // makes 2x more rotation
{
    struct timespec init_start;
    clock_gettime(CLOCK_MONOTONIC, &init_start);
    int pin;
    float acc_const, duration;
    int freq;
    if (!PyArg_ParseTuple(args, "ifif", &pin, &acc_const, &freq, &duration))
    {
        return NULL;
    }
    struct timespec calculations_start, calculations_end;
    int sleep_time, calculations_time, init_time; // nanoseconds
    SLEEP_PREP

    Py_BEGIN_ALLOW_THREADS

    float time_passed = 0.0;
    float impulse_duration = 1.0 / freq;

    clock_gettime(CLOCK_MONOTONIC, &calculations_start); 
    sleep_time = (int)(impulse_duration * 500000000); // nanoseconds
    time_passed += impulse_duration;
    impulse_duration = 1.0 / (freq + acc_const * time_passed);
    clock_gettime(CLOCK_MONOTONIC, &calculations_end);
    calculations_time = (calculations_end.tv_sec - calculations_start.tv_sec) * 1000000000 +
                        (calculations_end.tv_nsec - calculations_start.tv_nsec);
    init_time = (calculations_start.tv_sec - init_start.tv_sec) * 1000000000 +
                (calculations_start.tv_nsec - init_start.tv_nsec);

    while (time_passed < duration + impulse_duration)
    {
        gpioWrite(pin, 1);
        SLEEP(sleep_time - calculations_time)
        gpioWrite(pin, 0);
        SLEEP(sleep_time)
        sleep_time = (int)(impulse_duration * 500000000);
        time_passed += impulse_duration;
        impulse_duration = 1.0 / (freq + acc_const * time_passed);
    }
    Py_END_ALLOW_THREADS

    printf("Calculations time: %d ns\tInit time: %d ns\tLast impulse duration: %d ns\n", calculations_time, init_time, sleep_time*2);

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
