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
//#define INERTIA_PLATFORM2WHEEL_RATIO 5.65 
#define INERTIA_PLATFORM2WHEEL_RATIO 6.9
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
    write_dir(freq < 0 ? 0 : 1);
    if (freq < 0) {
        freq = -freq;
        acceleration = -acceleration;
    }

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

    write_dir(freq < 0 ? 0 : 1);
    if (freq < 0) {
        freq = -freq;
        acceleration = -acceleration;
    }

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
#define BREAK_TIME 0.5
#define REACH_TIME (0.5 - WAIT_TIME)
#define HALF_REACH_TIME (REACH_TIME/2)
#define MAX_FREQUENCY 7500
#define MAX_ACCELERATION 24000
#define MIN_FREQUENCY 200
#define NANO 1000000000
#define BACKWARD_FACTOR 0.000002

static void* rotation_server_thread_simple(void* arg)
{
    pthread_mutex_lock(&lock);
    SLEEP_PREP
    g_server_is_running = true;
    int dir = 0;
    int first = 1;
    long last_angle = 0;
    //long idle_delay = (int)floor(0.5/MIN_FREQUENCY * 500000000) - WRITING_TIME_NS;
    long idle_delay = 0;
    double acceleration = 0.0;
    long total_angle = 0;
    double start_frequency = MIN_FREQUENCY;

    while (g_server_is_running) {

        if (g_angle != 0) {

            total_angle += g_angle;
            g_angle = 0;

            pthread_mutex_unlock(&lock);

            SLEEP(BREAK_TIME * NANO)

            pthread_mutex_lock(&lock);
        } else {
            pthread_mutex_unlock(&lock);

            // Normalize to half rotation [-800, 800]
            total_angle %= 1600;
            if (total_angle > 800) {
                total_angle -= 1600;
            } else if (total_angle < -800) {
                total_angle += 1600;
            }

            acceleration = -total_angle * INERTIA_PLATFORM2WHEEL_RATIO / HALF_REACH_TIME / HALF_REACH_TIME;
            //acceleration = -2 * total_angle * INERTIA_PLATFORM2WHEEL_RATIO / REACH_TIME / REACH_TIME;
            start_frequency = copysignf(MIN_FREQUENCY, acceleration);
            generate_signal_prep(acceleration, start_frequency, HALF_REACH_TIME);
            //generate_signal(acceleration, start_frequency, REACH_TIME);
            
            total_angle = 0;
            pthread_mutex_lock(&lock);

            gpioWrite(ENABLE_PIN, 1);
            pthread_cond_wait(&cond, &lock);
            gpioWrite(ENABLE_PIN, 0);
        }

    }

    pthread_mutex_unlock(&lock);
    return NULL;
}

static void* rotation_server_thread(void* arg)
{
    pthread_mutex_lock(&lock);
    SLEEP_PREP
    g_server_is_running = true;
    int dir = 0;
    int first = 1;
    long last_angle = 0;
    //long idle_delay = (int)floor(0.5/MIN_FREQUENCY * 500000000) - WRITING_TIME_NS;
    long idle_delay = 0;
    double acceleration = 0.0;
    long total_angle = 0;
    double start_frequency = MIN_FREQUENCY;

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
            //total_angle += g_angle;
            total_angle -= (long)floor(g_angle * INERTIA_PLATFORM2WHEEL_RATIO);
            g_angle = 0;

            pthread_mutex_unlock(&lock);

            //SLEEP(WAIT_TIME * NANO)

            if (idle_delay == 0){
              start_frequency = copysignf(MIN_FREQUENCY, acceleration);
            }
            double end_frequency = start_frequency + acceleration*REACH_TIME;
            if (end_frequency*start_frequency > 0 && fabs(end_frequency) > MIN_FREQUENCY) {
              //generate_signal_prep(acceleration, MIN_FREQUENCY, HALF_REACH_TIME);
              generate_signal(acceleration, start_frequency, REACH_TIME);
            } else if (idle_delay == 0) {
              //generate_signal_prep(acceleration, MIN_FREQUENCY, HALF_REACH_TIME);
              generate_signal(acceleration, start_frequency, REACH_TIME);
            } else { // change of frequency sign during acceleration phase
              // just decelerate to 0
                double time_to_stop = fabs((copysignf(MIN_FREQUENCY, start_frequency) - start_frequency) / acceleration);
                generate_signal(acceleration, start_frequency, time_to_stop);
            }
            first = 0;

            pthread_mutex_lock(&lock);
        } else {
            //printf("STOP\n");
            pthread_mutex_unlock(&lock);
            
            if (first == 0) {
                double end_frequency = acceleration * REACH_TIME + start_frequency;
                if (fabs(end_frequency) < MIN_FREQUENCY) {
                    end_frequency = copysignf(MIN_FREQUENCY, end_frequency);
                }
                double rotation_backwards = copysign(1.0, -last_angle) * total_angle * total_angle * BACKWARD_FACTOR;
                double  waiting_time = WAIT_TIME;
                
                //double deceleration = (MIN_FREQUENCY - end_frequency) / WAIT_TIME;
                double deceleration = 2*(rotation_backwards - end_frequency * waiting_time)/(waiting_time*waiting_time);
                double max_acc = end_frequency * end_frequency;
                double decelerated_frequency = 1.0;
                if (fabs(deceleration) < max_acc && deceleration*end_frequency < 0) {
                    decelerated_frequency = end_frequency + deceleration * waiting_time;
                    if (fabs(decelerated_frequency) < MIN_FREQUENCY || decelerated_frequency*end_frequency < 0) {
                        deceleration = (copysignf(MIN_FREQUENCY,end_frequency) - end_frequency) / waiting_time;
                        decelerated_frequency = 0.0;
                    }
                    generate_signal(deceleration, end_frequency, waiting_time);
                } else if (fabs(deceleration) > MAX_ACCELERATION) {
                    deceleration = copysignf(MAX_ACCELERATION,deceleration);
                    double delta = sqrt(end_frequency*end_frequency + 2*rotation_backwards*deceleration);
                    waiting_time = (-end_frequency + delta)/deceleration;
                    if (waiting_time < 0) waiting_time = (-end_frequency - delta)/deceleration;
                    generate_signal(deceleration, end_frequency, waiting_time);
                } else if (deceleration*end_frequency > 0) {
                    generate_signal(deceleration, end_frequency, waiting_time);
                } else {
                    // instant stop
                    decelerated_frequency = 0.0;
                }
                if (decelerated_frequency != 0.0) {
                    decelerated_frequency = end_frequency + deceleration * waiting_time;
                }
                    
                if (fabs(decelerated_frequency) > MIN_FREQUENCY) {
                  idle_delay = labs((long)floor(500000000/decelerated_frequency)) - WRITING_TIME_NS;
                  start_frequency = decelerated_frequency;
                } else {
                  idle_delay = 0;
                  total_angle = 0;
                //   start_frequency = MIN_FREQUENCY; // moved above
                }
                printf("\ntotal_angle=%ld\nrotation_backwards=%f\ndeceleration=%f\nwaiting_time=%f\nend_frequency=%f\ndecelerated_frequency=%f\nidle_delay=%ld\n", total_angle, rotation_backwards, deceleration, waiting_time, end_frequency, decelerated_frequency, idle_delay);
                first = 1;
            }

            if (idle_delay > 0){
              //write_dir(dir == 0 ? 1 : 0);
              gpioWrite(STEP_PIN, 1);
              SLEEP(idle_delay)
              gpioWrite(STEP_PIN, 0);
              SLEEP(idle_delay)
              //double acceleration = -2 * 24 * INERTIA_PLATFORM2WHEEL_RATIO / 0.05 / 0.05;
              //generate_signal(acceleration, MIN_FREQUENCY, 0.05);
            } else {
              SLEEP(WAIT_TIME * NANO)
            }
            pthread_mutex_lock(&lock);

            if (idle_delay == 0){
              gpioWrite(ENABLE_PIN, 1);
              pthread_cond_wait(&cond, &lock);
              gpioWrite(ENABLE_PIN, 0);
            }
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

static PyObject* rotation_server_simple(PyObject* self, PyObject* noarg)
{
    bool server_was_running;
    int thread_created = 0;
    int thread_detached = 0;

    Py_BEGIN_ALLOW_THREADS
    pthread_mutex_lock(&lock);
    server_was_running = g_server_is_running;

    if (!server_was_running) {
        pthread_t thread_id;
        thread_created = pthread_create(&thread_id, NULL, rotation_server_thread_simple, NULL);
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
        "rotation_server_simple",
        rotation_server_simple,
        METH_NOARGS,
        "Starts the simple rotation server in a separate thread."
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
