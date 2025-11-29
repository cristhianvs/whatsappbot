/**
 * Ejemplo de uso del WhatsApp Client en tu aplicación
 */

const WhatsAppClient = require('./whatsapp-client');

// Inicializar cliente
const whatsapp = new WhatsAppClient({
    baseUrl: 'http://localhost:3001', // URL del WhatsApp Service
    timeout: 15000 // Timeout de 15 segundos
});

async function ejemploBasico() {
    try {
        console.log('🔍 Verificando disponibilidad del servicio...');
        
        // Verificar que el servicio esté disponible
        const isAvailable = await whatsapp.isAvailable();
        if (!isAvailable) {
            console.log('❌ Servicio no disponible, esperando...');
            const connected = await whatsapp.waitForService();
            if (!connected) {
                throw new Error('No se pudo conectar al servicio WhatsApp');
            }
        }
        
        console.log('✅ Servicio WhatsApp disponible');

        // Verificar estado de conexión WhatsApp
        console.log('📱 Verificando conexión WhatsApp...');
        const status = await whatsapp.getConnectionStatus();
        console.log('Estado:', status);

        if (!status.connected) {
            console.log('⚠️ WhatsApp no está conectado. Escanea el código QR.');
            return;
        }

        // Enviar mensaje de prueba
        console.log('📤 Enviando mensaje de prueba...');
        const result = await whatsapp.sendMessage(
            '+5215512345678', // Reemplaza con un número real
            '¡Hola desde mi aplicación! 🚀'
        );
        
        console.log('✅ Mensaje enviado:', result);

    } catch (error) {
        console.error('❌ Error:', error.message);
    }
}

// Ejemplo de integración con Express.js
function integrarConExpress(app) {
    // Endpoint para enviar mensajes desde tu API
    app.post('/api/whatsapp/send', async (req, res) => {
        try {
            const { to, message } = req.body;
            
            if (!to || !message) {
                return res.status(400).json({
                    error: 'Faltan parámetros: to y message son requeridos'
                });
            }

            const result = await whatsapp.sendMessage(to, message);
            res.json({
                success: true,
                data: result
            });

        } catch (error) {
            res.status(500).json({
                success: false,
                error: error.message
            });
        }
    });

    // Endpoint para verificar estado
    app.get('/api/whatsapp/status', async (req, res) => {
        try {
            const status = await whatsapp.getConnectionStatus();
            res.json(status);
        } catch (error) {
            res.status(500).json({
                error: error.message
            });
        }
    });

    // Endpoint de salud
    app.get('/api/whatsapp/health', async (req, res) => {
        try {
            const health = await whatsapp.getHealth();
            res.json(health);
        } catch (error) {
            res.status(500).json({
                error: error.message
            });
        }
    });
}

// Ejemplo de uso con notificaciones automáticas
async function sistemaNotificaciones() {
    const usuarios = [
        { telefono: '+5215512345678', nombre: 'Juan' },
        { telefono: '+5215587654321', nombre: 'María' }
    ];

    for (const usuario of usuarios) {
        try {
            await whatsapp.sendMessage(
                usuario.telefono,
                `Hola ${usuario.nombre}, tienes una nueva notificación en el sistema.`
            );
            console.log(`✅ Notificación enviada a ${usuario.nombre}`);
        } catch (error) {
            console.error(`❌ Error enviando a ${usuario.nombre}:`, error.message);
        }
    }
}

// Ejecutar ejemplo si se llama directamente
if (require.main === module) {
    ejemploBasico();
}

module.exports = {
    WhatsAppClient,
    integrarConExpress,
    sistemaNotificaciones
};