# Test Suite

Comprehensive test suite for the WhatsApp Support Bot system.

## Test Structure

```
tests/
├── unit/                    # Unit tests for individual components
│   ├── whatsapp-service/   # Node.js tests
│   ├── classifier-service/ # Python tests  
│   └── ticket-service/     # Python tests
├── integration/            # Integration tests between services
├── e2e/                   # End-to-end tests
├── fixtures/              # Test data and mocks
├── utils/                 # Test utilities and helpers
└── docker/                # Docker test configurations
```

## Running Tests

### All Tests
```bash
# Run all tests
npm run test:all

# Run with coverage
npm run test:coverage
```

### Service-Specific Tests

#### WhatsApp Service (Node.js)
```bash
cd services/whatsapp-service
npm test
npm run test:coverage
```

#### Python Services (Classifier & Ticket)
```bash
# Classifier Service
cd services/classifier-service
pytest tests/ -v --cov

# Ticket Service  
cd services/ticket-service
pytest tests/ -v --cov
```

### Integration Tests
```bash
# Start test environment
docker-compose -f tests/docker/docker-compose.test.yml up -d

# Run integration tests
npm run test:integration

# Cleanup
docker-compose -f tests/docker/docker-compose.test.yml down
```

## Test Configuration

### Environment Variables
Tests use separate environment configurations:
- `.env.test` - Test environment variables
- `tests/fixtures/` - Mock data and responses

### Test Databases
- Redis: Separate test database (db: 1)
- Mock external APIs (Zoho, OpenAI, etc.)

## Writing Tests

### Unit Test Guidelines
- Test individual functions/methods in isolation
- Mock external dependencies
- Use descriptive test names
- Include edge cases and error scenarios

### Integration Test Guidelines  
- Test service-to-service communication
- Use real Redis but mock external APIs
- Test complete workflows
- Verify message flow through Redis channels

### Fixtures and Mocks
- Store common test data in `fixtures/`
- Mock external API responses
- Use factories for generating test data