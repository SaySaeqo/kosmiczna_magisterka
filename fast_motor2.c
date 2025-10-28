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
#define ROTATION_PER_STEP (M_PI/800)
#define INERTIA_PLATFORM2WHEEL_RATIO 5.65 
//#define INERTIA_PLATFORM2WHEEL_RATIO 6.23
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

static void generate_signal_prep(double acceleration, int freq, double duration)
{
    SLEEP_PREP
    float time_passed = 0.0;
    float impulse_duration = fabs(1.0 / freq);

    int wait_times[20000];
    int wait_times_length = 0;

    while (time_passed < duration)
    {
        int sleep_time = (int)(impulse_duration * 500000000);
        time_passed += impulse_duration;
        freq = freq + acceleration * impulse_duration;
        impulse_duration = fabs(1.0 / freq);

        wait_times[wait_times_length++] = sleep_time;
    }

    int wait_times_reversed[20000];
    int wait_times_reversed_length = 0;
    time_passed = 0.0;

    while (time_passed < duration)
    {
        int sleep_time = (int)(impulse_duration * 500000000);
        time_passed += impulse_duration;
        freq = freq - acceleration * impulse_duration;
        impulse_duration = fabs(1.0 / freq);

        wait_times_reversed[wait_times_reversed_length++] = sleep_time;
    }
    
    for (int i = 0; i < wait_times_length; i++)
    {
        gpioWrite(STEP_PIN, 1);
        SLEEP(wait_times[i] - WRITING_TIME_NS)
        gpioWrite(STEP_PIN, 0);
        SLEEP(wait_times[i] - WRITING_TIME_NS)
    }

    for (int i = 0; i < wait_times_reversed_length; i++)
    {
        gpioWrite(STEP_PIN, 1);
        SLEEP(wait_times_reversed[i] - WRITING_TIME_NS)
        gpioWrite(STEP_PIN, 0);
        SLEEP(wait_times_reversed[i] - WRITING_TIME_NS)
    }

    return;
}

static void generate_signal(double acceleration, double freq, double duration)
{
    // Make sure that this function is not called too quickly 
    while (clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &signal_min_start, NULL) == EINTR);

    // Start signal ASAP
    gpioWrite(STEP_PIN, 1);

    // Prepare variable for signal generation
    SLEEP_PREP
    double time_passed = 0.0;
    double impulse_duration = 1.0 / freq;
    double sleep_time;

    // Finish first impulse (started before getting parameters)
    sleep_time = (int)(impulse_duration * 500000000);
    time_passed += impulse_duration;
    impulse_duration = 1.0 / (freq + acceleration * time_passed);
    SLEEP(sleep_time-WRITING_TIME_NS-CALCULATION_TIME_NS)
    gpioWrite(STEP_PIN, 0);

    // Generate the rest of the impulses
    while (time_passed < duration)
    {
        SLEEP(sleep_time-WRITING_TIME_NS-CALCULATION_TIME_NS)
        sleep_time = (int)(impulse_duration * 500000000);
        time_passed += impulse_duration;
        impulse_duration = 1.0 / (freq + acceleration * time_passed);
        gpioWrite(STEP_PIN, 1);
        SLEEP(sleep_time-WRITING_TIME_NS)
        gpioWrite(STEP_PIN, 0);
    }

    // Set minimum time for next signal
    clock_gettime(CLOCK_MONOTONIC, &signal_min_start);
    const long long nsec = signal_min_start.tv_nsec + sleep_time - WRITING_TIME_NS;
    signal_min_start.tv_sec += nsec / 1000000000;
    signal_min_start.tv_nsec = nsec % 1000000000;

    return;
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

static void generate_signal_internal(double freq, double duration) {
    double impulse_duration = fabs(1.0 / freq);
    int sleep_time = (int)(impulse_duration * 500000000) - WRITING_TIME_NS;
    int impulses_count = (int)floor(duration / impulse_duration);
    SLEEP_PREP

    for (int i = 0; i < impulses_count; i++)
    {
        gpioWrite(STEP_PIN, 1);
        SLEEP(sleep_time)
        gpioWrite(STEP_PIN, 0);
        SLEEP(sleep_time)
    }
}

static pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t cond = PTHREAD_COND_INITIALIZER;
static bool g_server_is_running = false;
#define NO_VALUE -10
static struct Quaternion g_position = {NO_VALUE, NO_VALUE, NO_VALUE, 1};
static double g_frequency = 0.0;
static double g_acceleration = 0.0;
static long g_angle = 0;
#define INTERVAL 0.05
#define WAIT_TIME 0.1
#define REACH_TIME (0.5 - WAIT_TIME)
#define HALF_REACH_TIME (REACH_TIME/2)
#define MAX_FREQUENCY 7500
#define MAX_ACCELERATION 24000
#define MIN_FREQUENCY 200
#define NANO 1000000000

static void* rotation_server_thread(void* arg)
{
    pthread_mutex_lock(&lock);
    SLEEP_PREP
    g_server_is_running = true;
    int dir = 0;
    int first = 0;
    long last_angle = 0;
    long idle_delay = (int)floor(0.5/MIN_FREQUENCY * 500000000) - WRITING_TIME_NS;
    double acceleration = 0.0;

    while (g_server_is_running) {

        if (g_angle != 0) {

            // Normalize to half rotation [-800, 800]
            g_angle %= 1600;
            if (g_angle > 800) {
                g_angle -= 1600;
            } else if (g_angle < -800) {
                g_angle += 1600;
            }

            //printf("g_angle=%ld\n", g_angle);
            //acceleration = -g_angle * INERTIA_PLATFORM2WHEEL_RATIO / HALF_REACH_TIME / HALF_REACH_TIME;
            acceleration = -2 * g_angle * INERTIA_PLATFORM2WHEEL_RATIO / REACH_TIME / REACH_TIME;
            last_angle = g_angle;
            g_angle = 0;

            pthread_mutex_unlock(&lock);

            dir = acceleration < 0.0 ? 0 : 1;
            write_dir(dir);
            acceleration = fabs(acceleration);
            SLEEP(WAIT_TIME * NANO)
            //generate_signal_prep(acceleration, MIN_FREQUENCY, HALF_REACH_TIME);
            generate_signal(acceleration, MIN_FREQUENCY, REACH_TIME);
            first = 0;

            pthread_mutex_lock(&lock);
        } else {
            //printf("STOP\n");
            pthread_mutex_unlock(&lock);
            
            if (first == 0) {
             long idle_frequency = acceleration * REACH_TIME + MIN_FREQUENCY;
             idle_frequency /= 4;
             idle_delay = labs((long)floor(500000000/idle_frequency) - WRITING_TIME_NS);
             first = 1;
            }

            //write_dir(dir == 0 ? 1 : 0);
            gpioWrite(STEP_PIN, 1);
            SLEEP(idle_delay)
            gpioWrite(STEP_PIN, 0);
            SLEEP(idle_delay)
            //double acceleration = -2 * 24 * INERTIA_PLATFORM2WHEEL_RATIO / 0.05 / 0.05;
            //generate_signal(acceleration, MIN_FREQUENCY, 0.05);

            // SLEEP(WAIT_TIME * NANO)
            pthread_mutex_lock(&lock);

            // gpioWrite(ENABLE_PIN, 1);
            // pthread_cond_wait(&cond, &lock);
            // gpioWrite(ENABLE_PIN, 0);
        }

    }

    pthread_mutex_unlock(&lock);
    return NULL;
}

static PyObject* rotation_server(PyObject* self, PyObject* noarg)
{
    bool server_was_running;
    int thread_created = 0;
    int thread_detached = 0;

    Py_BEGIN_ALLOW_THREADS
    pthread_mutex_lock(&lock);
    server_was_running = g_server_is_running;

    if (!server_was_running) {
        pthread_t thread_id;
        thread_created = pthread_create(&thread_id, NULL, rotation_server_thread, NULL);
        if (thread_created != 0) {
            thread_detached = pthread_detach(thread_id);
        }
    }
    pthread_mutex_unlock(&lock);
    Py_END_ALLOW_THREADS

    if (server_was_running) {
        PyErr_SetString(PyExc_Exception, "Rotation server is already running");
        return NULL;
    }
    if (thread_created != 0) {
        PyErr_SetString(PyExc_Exception, "Failed to create rotation server thread");
        return NULL;
    }
    if (thread_detached != 0) {
        PyErr_SetString(PyExc_Exception, "Failed to detach rotation server thread");
        return NULL;
    }

    Py_RETURN_NONE;
}


static PyObject* rotation_client(PyObject* self, PyObject* args)
{
    long angle;
    if (!PyArg_ParseTuple(args, "l", &angle))
    {
        return NULL;
    }

    if (g_server_is_running == false) {
        PyErr_SetString(PyExc_Exception, "Rotation server is not running");
        return NULL;
    }

    Py_BEGIN_ALLOW_THREADS

    pthread_mutex_lock(&lock);

    if (labs(angle) > 24) {
        g_angle += angle;
        pthread_cond_signal(&cond);
    }

    pthread_mutex_unlock(&lock);
    Py_END_ALLOW_THREADS

    Py_RETURN_NONE;
}

static PyObject* print_globals(PyObject* self, PyObject* noarg)
{
    pthread_mutex_lock(&lock);
    long angle = g_angle;
    double frequency = g_frequency;
    double acceleration = g_acceleration;
    pthread_mutex_unlock(&lock);
    printf("g_angle: %ld, g_frequency: %f, g_acceleration: %f\n", angle, frequency, acceleration);
    Py_RETURN_NONE;
}

static PyObject* stop_rotation(PyObject* self, PyObject* noarg)
{
    Py_BEGIN_ALLOW_THREADS
    pthread_mutex_lock(&lock);
    g_server_is_running = false;
    pthread_mutex_unlock(&lock);
    Py_END_ALLOW_THREADS
    Py_RETURN_NONE;
}

static PyObject* cleanup_motor(PyObject* self, PyObject* noarg)
{
    ASSERT_SUCCESS_NULL(gpioWrite(ENABLE_PIN, 1), "Failed to write to GPIO");
    Py_RETURN_NONE;
}

static void fast_motor2_atexit(void) {
    g_server_is_running = false;
    gpioWrite(ENABLE_PIN, 1);
    gpioTerminate();
}

static int
fast_motor2_module_exec(PyObject *m)
{
    ASSERT_SUCCESS(gpioInitialise(), "Failed to initialize PIGPIO");
    ASSERT_SUCCESS(Py_AtExit(fast_motor2_atexit), "Failed to register PIGPIO exit handler");
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
    ASSERT_SUCCESS(gpioWrite(M3_PIN, 0), "Failed to write to GPIO");
    clock_gettime(CLOCK_MONOTONIC, &signal_min_start);
    return 0;
}

static PyObject* setup_motor(PyObject* self, PyObject* noarg)
{
    ASSERT_SUCCESS_NULL(gpioWrite(ENABLE_PIN, 0), "Failed to write to GPIO");
    Py_RETURN_NONE;
}


static PyMethodDef fast_motor2_funcs[] = {
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

static PyModuleDef_Slot fast_motor2_module_slots[] = {
    {Py_mod_exec, fast_motor2_module_exec},
    {0, NULL}
};

static struct PyModuleDef fast_motor2_module = {
    .m_base = PyModuleDef_HEAD_INIT,
    .m_name = "fast_motor2",
    .m_size = 0, // allow module re-initialization
    .m_doc = "Module for accelerating stepper motor wave generations.",
    .m_methods = fast_motor2_funcs,
    .m_slots = fast_motor2_module_slots,
};

PyMODINIT_FUNC PyInit_fast_motor2(void) {
    return PyModuleDef_Init(&fast_motor2_module);
}
