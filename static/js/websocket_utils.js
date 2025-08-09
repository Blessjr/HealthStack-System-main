class ChatSocket {
    constructor(conversationId, options = {}) {
        this.conversationId = conversationId;
        this.options = {
            heartbeatInterval: 30000,
            reconnectDelay: 5000,
            ...options
        };
        this.connect();
    }

    connect() {
        this.socket = new WebSocket(
            `ws://${window.location.host}/ws/chat/${this.conversationId}/`
        );

        this.socket.onopen = () => {
            console.log('WebSocket Connected');
            this.heartbeat = setInterval(() => {
                this.send({type: 'heartbeat'});
            }, this.options.heartbeatInterval);

            // Send initialization message if needed
            if (this.options.initMessage) {
                this.send(this.options.initMessage);
            }
        };

        this.socket.onmessage = (event) => {
            if (this.options.onMessage) {
                this.options.onMessage(JSON.parse(event.data));
            }
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket Error:', error);
            this.reconnect();
        };

        this.socket.onclose = (e) => {
            console.log('Socket closed. Reconnecting...', e.reason);
            clearInterval(this.heartbeat);
            this.reconnect();
        };
    }

    send(data) {
        if (this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(data));
        } else {
            console.warn('WebSocket not ready. Queueing message:', data);
            setTimeout(() => this.send(data), 1000);
        }
    }

    reconnect() {
        setTimeout(() => {
            console.log('Attempting to reconnect...');
            this.connect();
        }, this.options.reconnectDelay);
    }

    close() {
        clearInterval(this.heartbeat);
        this.socket.close();
    }
}

// Automatic initialization based on page context
document.addEventListener('DOMContentLoaded', () => {
    // Patient chat interface
    if (document.querySelector('#chat-interface')) {
        const conversationId = document.querySelector('#chat-interface').dataset.conversationId || 'patient_default';
        new ChatSocket(conversationId, {
            onMessage: (data) => {
                // Handle incoming messages for patient
                console.log('Patient received:', data);
                // Add your message rendering logic here
            }
        });
    }

    // Doctor chat panel
    if (document.querySelector('#doctor-chat-panel')) {
        const doctorId = document.querySelector('#doctor-chat-panel').dataset.doctorId || 'doctor_default';
        new ChatSocket(`doctor_${doctorId}`, {
            onMessage: (data) => {
                // Handle incoming messages for doctor
                console.log('Doctor received:', data);
                // Add notification logic here
            },
            initMessage: {
                type: 'doctor_online',
                status: 'active'
            }
        });
    }
});