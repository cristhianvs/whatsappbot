/**
 * Ejemplo de uso del Message Listener con Redis
 */

const WhatsAppMessageListener = require('./message-listener');

// Crear instancia del listener
const listener = new WhatsAppMessageListener({
    redisUrl: 'redis://localhost:6379'
});

async function ejemploCompleto() {
    try {
        // Conectar al listener
        await listener.connect();

        // Manejar mensajes de texto
        listener.onMessage('text', (message) => {
            console.log(`💬 Mensaje de texto de ${message.from_user}:`);
            console.log(`   "${message.text}"`);
            
            // Aquí puedes procesar el mensaje en tu aplicación
            // Ejemplo: guardar en base de datos, enviar respuesta automática, etc.
            procesarMensajeTexto(message);
        });

        // Manejar imágenes
        listener.onMessage('image', (message) => {
            console.log(`🖼️ Imagen recibida de ${message.from_user}`);
            if (message.media_url) {
                console.log(`   URL: ${message.media_url}`);
            }
            
            procesarImagen(message);
        });

        // Manejar todos los tipos de mensajes
        listener.onMessage('all', (message) => {
            // Log general de todos los mensajes
            registrarMensajeEnBD(message);
        });

        console.log('🎧 Sistema de escucha iniciado. Presiona Ctrl+C para salir.');

        // Manejar cierre graceful
        process.on('SIGINT', async () => {
            console.log('\n🛑 Cerrando listener...');
            await listener.disconnect();
            process.exit(0);
        });

    } catch (error) {
        console.error('❌ Error:', error);
        process.exit(1);
    }
}

// Funciones de ejemplo para procesar mensajes
function procesarMensajeTexto(message) {
    // Ejemplo: respuesta automática para ciertos mensajes
    if (message.text.toLowerCase().includes('hola')) {
        console.log('🤖 Enviando respuesta automática...');
        // Aquí podrías enviar una respuesta usando el WhatsApp Client
    }
    
    // Ejemplo: guardar en base de datos
    // database.saveMessage(message);
}

function procesarImagen(message) {
    // Ejemplo: procesar imagen recibida
    console.log('📸 Procesando imagen...');
    // Aquí podrías descargar y procesar la imagen
}

function registrarMensajeEnBD(message) {
    // Ejemplo: log general en base de datos
    console.log(`📝 Registrando mensaje ${message.id} en BD`);
    // database.logMessage(message);
}

// Ejemplo de integración con sistema de tickets
function integrarConSistemaTickets() {
    listener.onMessage('text', async (message) => {
        // Si el mensaje contiene "soporte" o "ayuda", crear ticket
        if (message.text.toLowerCase().includes('soporte') || 
            message.text.toLowerCase().includes('ayuda')) {
            
            console.log('🎫 Creando ticket de soporte...');
            
            const ticket = {
                usuario: message.from_user,
                mensaje: message.text,
                fecha: new Date(message.timestamp),
                canal: 'whatsapp',
                estado: 'abierto'
            };
            
            // Crear ticket en tu sistema
            // await ticketSystem.createTicket(ticket);
            
            console.log('✅ Ticket creado para', message.from_user);
        }
    });
}

// Ejemplo de bot de respuestas automáticas
function configurarBotRespuestas() {
    const respuestasAutomaticas = {
        'hola': '¡Hola! ¿En qué puedo ayudarte?',
        'horario': 'Nuestro horario de atención es de 9:00 AM a 6:00 PM',
        'contacto': 'Puedes contactarnos al teléfono (555) 123-4567',
        'gracias': '¡De nada! ¿Hay algo más en lo que pueda ayudarte?'
    };

    listener.onMessage('text', (message) => {
        const texto = message.text.toLowerCase();
        
        for (const [palabra, respuesta] of Object.entries(respuestasAutomaticas)) {
            if (texto.includes(palabra)) {
                console.log(`🤖 Enviando respuesta automática a ${message.from_user}`);
                // Aquí enviarías la respuesta usando el WhatsApp Client
                // whatsappClient.sendMessage(message.from_user, respuesta);
                break;
            }
        }
    });
}

// Ejecutar ejemplo si se llama directamente
if (require.main === module) {
    ejemploCompleto();
}

module.exports = {
    WhatsAppMessageListener,
    integrarConSistemaTickets,
    configurarBotRespuestas
};