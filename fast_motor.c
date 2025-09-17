#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <pigpio.h>
#include <stdio.h>
#include <time.h>
#include <math.h>
#include <stdbool.h>
#include <pthread.h>
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
#define INERTIA_PLATFORM2WHEEL_RATIO 2.74
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


static struct timespec signal_min_start;



static int dir_value = 0;

static void write_dir(int value)
{
    if (value != dir_value)
    {
        gpioWrite(DIR_PIN, value);
        dir_value = value;
    }
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
    // Make sure that this function is not called too quickly 
    while (clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &signal_min_start, NULL) == EINTR);

    // Start signal ASAP
    gpioWrite(STEP_PIN, 1);

    // Start "init time" measurement
    struct timespec start, end;
    int init_time;
    clock_gettime(CLOCK_MONOTONIC, &start);

    // Get parameters
    double duration, acceleration;
    double freq;
    if (!PyArg_ParseTuple(args, "(ddd)", &acceleration, &freq, &duration))
    {
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS // Python functions cannot be within this block
    
    // Correct parameters by controlling direction
    if (freq > 0.0) {
        write_dir(0);
    } else {
        write_dir(1);
        freq = -freq;
        acceleration = -acceleration;
    }
    
    // Prepare variable for signal generation
    SLEEP_PREP
    double time_passed = 0.0;
    double impulse_duration = 1.0 / freq;
    double sleep_time;
    const double acc_const = acceleration * INERTIA_PLATFORM2WHEEL_RATIO / ROTATION_PER_STEP;

    // Get "init time"
    clock_gettime(CLOCK_MONOTONIC, &end);
    init_time = (end.tv_sec - start.tv_sec) * 1000000000 + (end.tv_nsec - start.tv_nsec);

    // Finish first impulse (started before getting parameters)
    sleep_time = (int)(impulse_duration * 500000000);
    time_passed += impulse_duration;
    impulse_duration = 1.0 / (freq + acc_const * time_passed);
    SLEEP(sleep_time-WRITING_TIME_NS-CALCULATION_TIME_NS-init_time)
    gpioWrite(STEP_PIN, 0);

    // Generate the rest of the impulses
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

    // Set minimum time for next signal
    clock_gettime(CLOCK_MONOTONIC, &signal_min_start);
    const long long nsec = signal_min_start.tv_nsec + sleep_time - WRITING_TIME_NS;
    signal_min_start.tv_sec += nsec / 1000000000;
    signal_min_start.tv_nsec = nsec % 1000000000;

    Py_END_ALLOW_THREADS

    Py_RETURN_NONE;
}

struct Quaternion {

    double x;
    double y;
    double z;
    double w;
};

static double get_angle(struct Quaternion q1, struct Quaternion q2)
{
    struct Quaternion cf = {
        .x = -q1.x,
        .y = -q1.y,
        .z = -q1.z,
        .w = q1.w
    };
    struct Quaternion dp = {
        .x = q2.w*cf.x + q2.x*cf.w + q2.y*cf.z - q2.z*cf.y,
        .y = q2.w*cf.y - q2.x*cf.z + q2.y*cf.w + q2.z*cf.x,
        .z = q2.w*cf.z + q2.x*cf.y - q2.y*cf.x + q2.z*cf.w,
        .w = q2.w*cf.w - q2.x*cf.x - q2.y*cf.y - q2.z*cf.z
    };

    return atan2(2*(dp.w*dp.y + dp.x*dp.z), 1 - 2*(dp.y*dp.y + dp.z*dp.z));
}

static double clamp(double value, double min, double max) {
    if (value < min) return min;
    if (value > max) return max;
    return value;
}


static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t cond = PTHREAD_COND_INITIALIZER;
static bool g_server_is_running = false;
#define NO_VALUE -10
static struct Quaternion g_position = {NO_VALUE, NO_VALUE, NO_VALUE, 1};
static double g_frequency = 0;
static double g_acceleration = 0;
static long g_angle = 0;
#define INTERVAL 0.1
#define REACH_TIME (INTERVAL*2)
#define MAX_FREQUENCY 16000
#define MAX_ACCELERATION 24000
#define MIN_FREQUENCY 200

static void* rotation_server_thread(void* arg)
{
    pthread_mutex_lock(&lock);
    SLEEP_PREP
    g_server_is_running = true;

    while (g_server_is_running) {
        
        // Update frequency based on acceleration
        if (g_frequency != 0) {
            g_frequency += g_acceleration/fabs(g_frequency);

            g_frequency = clamp(g_frequency, -MAX_FREQUENCY, MAX_FREQUENCY);
            g_frequency = fabs(g_frequency) < MIN_FREQUENCY ? 0.0 : g_frequency;
        } else {
            g_frequency = copysign(MIN_FREQUENCY, g_acceleration);
        }

        // Generate step signal or wait
        if (g_angle == 0) {
            g_frequency = 0.0;
            gpioWrite(ENABLE_PIN, 1);
            pthread_cond_wait(&cond, &lock);
            gpioWrite(ENABLE_PIN, 0);
        } else if (g_frequency != 0) {
            int dir = g_frequency < 0 ? 1 : 0;
            write_dir(dir);
            long sleep_time = labs((long)(500000000/g_frequency));

            pthread_mutex_unlock(&lock);
            SLEEP(sleep_time)
            gpioWrite(STEP_PIN, 1);
            SLEEP(sleep_time)
            gpioWrite(STEP_PIN, 0);
            pthread_mutex_lock(&lock);

            g_angle += dir ? -1 : 1;
        } else if (g_acceleration != 0) {
            int dir = g_acceleration < 0 ? 1 : 0;
            write_dir(dir);

            pthread_mutex_unlock(&lock);
            long sleep_time = 1000000000/MIN_FREQUENCY;
            SLEEP(sleep_time)
            pthread_mutex_lock(&lock);
            
            g_angle += dir ? -1 : 1;
        }

    }

    pthread_mutex_unlock(&lock);
    return NULL;
}

static PyObject* rotation_server(PyObject* self)
{
    if (g_server_is_running) {
        PyErr_SetString(PyExc_Exception, "Rotation server is already running");
        return NULL;
    }

    pthread_t thread_id;
    if (pthread_create(&thread_id, NULL, rotation_server_thread, NULL) != 0) {
        PyErr_SetString(PyExc_Exception, "Failed to create rotation server thread");
        return NULL;
    }
    pthread_detach(thread_id);

    Py_RETURN_NONE;
}


static PyObject* rotation_client(PyObject* self, PyObject* args)
{
    double x, y, z, w;
    if (!PyArg_ParseTuple(args, "dddd", &x, &y, &z, &w))
    {
        return NULL;
    }

    struct Quaternion target_position = {x, y, z, w};
    if (g_position.x == NO_VALUE) {
        g_position = target_position;
        Py_RETURN_NONE;
    }
    if (g_server_is_running == false) {
        PyErr_SetString(PyExc_Exception, "Rotation server is not running");
        return NULL;
    }
    
    Py_BEGIN_ALLOW_THREADS

    // Calculate the angle difference
    double angle = get_angle(g_position, target_position);
    long angle_steps = (long)floor(angle / ROTATION_PER_STEP);
    pthread_mutex_lock(&lock);
    g_angle += angle_steps;

    if (g_angle > 0) {
        // Update acceleration to reach the target angle in the given time
        g_acceleration = (2*g_angle-g_frequency*REACH_TIME)/(REACH_TIME*REACH_TIME);
        g_acceleration = clamp(g_acceleration, -MAX_ACCELERATION, MAX_ACCELERATION);
        g_acceleration *= INERTIA_PLATFORM2WHEEL_RATIO; // adjust for platform angle

        if (g_angle == angle_steps) {
            pthread_cond_signal(&cond);
        }
    }
    pthread_mutex_unlock(&lock);
    Py_END_ALLOW_THREADS

    Py_RETURN_NONE;
}

static PyObject* print_globals(PyObject* self)
{
    pthread_mutex_lock(&lock);
    printf("g_angle: %ld, g_frequency: %f, g_acceleration: %f\n", g_angle, g_frequency, g_acceleration);
    pthread_mutex_unlock(&lock);
    Py_RETURN_NONE;
}

static PyObject* stop_rotation(PyObject* self)
{
    Py_BEGIN_ALLOW_THREADS
    pthread_mutex_lock(&lock);
    g_server_is_running = false;
    pthread_mutex_unlock(&lock);
    Py_END_ALLOW_THREADS
    Py_RETURN_NONE;
}

static PyObject* cleanup_motor(PyObject* self)
{
    ASSERT_SUCCESS_NULL(gpioWrite(ENABLE_PIN, 1), "Failed to write to GPIO");
    Py_RETURN_NONE;
}

static void fast_motor_atexit(void) {
    g_server_is_running = false;
    gpioWrite(ENABLE_PIN, 1);
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
    ASSERT_SUCCESS(gpioWrite(STEP_PIN, 0), "Failed to write to GPIO");
    ASSERT_SUCCESS(gpioWrite(DIR_PIN, 0), "Failed to write to GPIO");
    ASSERT_SUCCESS(gpioWrite(M1_PIN, 1), "Failed to write to GPIO");
    ASSERT_SUCCESS(gpioWrite(M2_PIN, 1), "Failed to write to GPIO");
    ASSERT_SUCCESS(gpioWrite(M3_PIN, 1), "Failed to write to GPIO");
    clock_gettime(CLOCK_MONOTONIC, &signal_min_start);
    return 0;
}

static PyObject* setup_motor(PyObject* self)
{
    ASSERT_SUCCESS_NULL(gpioWrite(ENABLE_PIN, 0), "Failed to write to GPIO");
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
    {    
        "rotation_server",
        rotation_server,
        METH_NOARGS,
        "Starts the rotation server in a separate thread."
    },
    {    
        "rotation_client",
        rotation_client,
        METH_VARARGS,
        "Sends target rotation to the server."
    },
    {    
        "stop_rotation",
        stop_rotation,
        METH_NOARGS,
        "Stops the rotation server."
    },
    {    
        "print_globals",
        print_globals,
        METH_NOARGS,
        "Prints global variables for debugging."
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
