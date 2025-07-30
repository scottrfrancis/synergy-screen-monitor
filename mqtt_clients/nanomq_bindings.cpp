/**
 * NanoMQ Python Bindings
 * 
 * This module provides Python bindings for NanoSDK MQTT client functionality.
 * Uses pybind11 for seamless Python-C++ integration.
 */

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h>
#include <memory>
#include <string>
#include <functional>
#include <thread>
#include <chrono>
#include <atomic>
#include <mutex>

extern "C" {
#include <nng/nng.h>
#include <nng/mqtt/mqtt_client.h>
#include <nng/supplemental/util/platform.h>
}

namespace py = pybind11;

class NanoMQTTClient {
private:
    nng_socket sock;
    std::atomic<bool> connected{false};
    std::atomic<bool> running{false};
    std::string broker_url;
    std::thread worker_thread;
    std::mutex callback_mutex;
    std::function<void(const std::string&, const std::string&)> message_callback;
    
public:
    NanoMQTTClient(const std::string& broker, int port) {
        broker_url = "mqtt-tcp://" + broker + ":" + std::to_string(port);
        
        int rv = nng_mqtt_client_open(&sock);
        if (rv != 0) {
            throw std::runtime_error("Failed to open MQTT client: " + std::string(nng_strerror(rv)));
        }
    }
    
    ~NanoMQTTClient() {
        disconnect();
        if (worker_thread.joinable()) {
            worker_thread.join();
        }
        nng_close(sock);
    }
    
    bool connect(const std::string& client_id = "") {
        if (connected.load()) {
            return true;
        }
        
        // Set client ID if provided using socket option
        if (!client_id.empty()) {
            int rv = nng_socket_set_string(sock, NNG_OPT_MQTT_CLIENT_ID, client_id.c_str());
            if (rv != 0) {
                return false;
            }
        }
        
        // Set keep alive using socket option
        nng_duration keep_alive = 60000; // 60 seconds in milliseconds
        int rv = nng_socket_set_ms(sock, NNG_OPT_MQTT_KEEP_ALIVE, keep_alive);
        if (rv != 0) {
            return false;
        }
        
        // Create and start dialer
        rv = nng_dial(sock, broker_url.c_str(), nullptr, NNG_FLAG_NONBLOCK);
        if (rv != 0) {
            return false;
        }
        
        // For MQTT, connection success is typically immediate with NNG_FLAG_NONBLOCK
        // Wait a brief moment for the connection to establish
        nng_msleep(500);
        connected.store(true);
        
        return false;
    }
    
    void disconnect() {
        if (connected.load()) {
            running.store(false);
            connected.store(false);
            // Socket will be closed in destructor
        }
    }
    
    bool is_connected() const {
        return connected.load();
    }
    
    bool publish(const std::string& topic, const std::string& payload, int qos = 0) {
        if (!connected.load()) {
            return false;
        }
        
        nng_msg* msg;
        int rv = nng_mqtt_msg_alloc(&msg, 0);
        if (rv != 0) {
            return false;
        }
        
        // Set message type to PUBLISH
        nng_mqtt_msg_set_packet_type(msg, NNG_MQTT_PUBLISH);
        
        // Set topic and payload
        nng_mqtt_msg_set_publish_topic(msg, topic.c_str());
        nng_mqtt_msg_set_publish_payload(msg, 
            const_cast<uint8_t*>(reinterpret_cast<const uint8_t*>(payload.data())), 
            payload.length());
        nng_mqtt_msg_set_publish_qos(msg, qos);
        
        // Send message
        rv = nng_sendmsg(sock, msg, NNG_FLAG_NONBLOCK);
        if (rv != 0) {
            nng_msg_free(msg);
            return false;
        }
        
        return true;
    }
    
    bool subscribe(const std::string& topic, int qos = 0) {
        if (!connected.load()) {
            return false;
        }
        
        nng_msg* msg;
        int rv = nng_mqtt_msg_alloc(&msg, 0);
        if (rv != 0) {
            return false;
        }
        
        // Set message type to SUBSCRIBE
        nng_mqtt_msg_set_packet_type(msg, NNG_MQTT_SUBSCRIBE);
        
        // Create topic QoS array properly
        nng_mqtt_topic_qos* topics = nng_mqtt_topic_qos_array_create(1);
        if (!topics) {
            nng_msg_free(msg);
            return false;
        }
        nng_mqtt_topic_qos_array_set(topics, 0, topic.c_str(), topic.length(), qos, 0, 0, 0);
        nng_mqtt_msg_set_subscribe_topics(msg, topics, 1);
        nng_mqtt_topic_qos_array_free(topics, 1);
        
        // Send subscription
        rv = nng_sendmsg(sock, msg, NNG_FLAG_NONBLOCK);
        if (rv != 0) {
            nng_msg_free(msg);
            return false;
        }
        
        return true;
    }
    
    void set_message_callback(std::function<void(const std::string&, const std::string&)> callback) {
        std::lock_guard<std::mutex> lock(callback_mutex);
        message_callback = callback;
    }
    
    void start_message_loop() {
        if (running.load()) {
            return;
        }
        
        running.store(true);
        worker_thread = std::thread([this]() {
            message_loop();
        });
    }
    
    void stop_message_loop() {
        running.store(false);
        if (worker_thread.joinable()) {
            worker_thread.join();
        }
    }
    
private:
    void message_loop() {
        while (running.load() && connected.load()) {
            nng_msg* msg;
            int rv = nng_recvmsg(sock, &msg, NNG_FLAG_NONBLOCK);
            
            if (rv == 0) {
                handle_message(msg);
                nng_msg_free(msg);
            } else if (rv == NNG_EAGAIN) {
                // No message available, sleep briefly
                nng_msleep(10);
            } else {
                // Error receiving message
                break;
            }
        }
    }
    
    void handle_message(nng_msg* msg) {
        nng_mqtt_packet_type packet_type = nng_mqtt_msg_get_packet_type(msg);
        
        if (packet_type == NNG_MQTT_PUBLISH) {
            uint32_t topic_len;
            const char* topic = nng_mqtt_msg_get_publish_topic(msg, &topic_len);
            uint32_t payload_len;
            const uint8_t* payload = nng_mqtt_msg_get_publish_payload(msg, &payload_len);
            
            if (topic && payload) {
                std::string topic_str(topic, topic_len);
                std::string payload_str(reinterpret_cast<const char*>(payload), payload_len);
                
                std::lock_guard<std::mutex> lock(callback_mutex);
                if (message_callback) {
                    message_callback(topic_str, payload_str);
                }
            }
        }
    }
};

PYBIND11_MODULE(nanomq_bindings, m) {
    m.doc() = "NanoMQ Python bindings for MQTT client functionality";
    
    py::class_<NanoMQTTClient>(m, "NanoMQTTClient")
        .def(py::init<const std::string&, int>(), "Create MQTT client", 
             py::arg("broker"), py::arg("port"))
        .def("connect", &NanoMQTTClient::connect, "Connect to MQTT broker",
             py::arg("client_id") = "")
        .def("disconnect", &NanoMQTTClient::disconnect, "Disconnect from MQTT broker")
        .def("is_connected", &NanoMQTTClient::is_connected, "Check connection status")
        .def("publish", &NanoMQTTClient::publish, "Publish message to topic",
             py::arg("topic"), py::arg("payload"), py::arg("qos") = 0)
        .def("subscribe", &NanoMQTTClient::subscribe, "Subscribe to topic",
             py::arg("topic"), py::arg("qos") = 0)
        .def("set_message_callback", &NanoMQTTClient::set_message_callback,
             "Set callback for received messages")
        .def("start_message_loop", &NanoMQTTClient::start_message_loop,
             "Start message receiving loop")
        .def("stop_message_loop", &NanoMQTTClient::stop_message_loop,
             "Stop message receiving loop");
}