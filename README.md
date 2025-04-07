# 4D QuickBooks Online Integration

Integration between 4D EMR and QuickBooks Online for automated invoice management and financial synchronization.

## Overview

This project provides a bridge between 4D EMR's billing system and QuickBooks Online, enabling automated:
- Invoice creation and management
- Payment tracking
- Financial data synchronization

## Requirements

- Python 3.8+
- QuickBooks Online account with API access
- Domain with SSL certificate (for production)

## Quick Start

1. Clone the repository:
```bash
git clone https://github.com/Sal-Romano/4d.qbo.git
cd 4d.qbo
```

2. Follow the setup guides in our documentation:
- [Development Setup](docs/development.md) - For local development
- [Production Setup](docs/production.md) - For deploying to production
- [Environment Configuration](docs/configuration.md) - Details about all configuration options

## Project Structure

```
.
├── scripts/
│   ├── qbo_manager.py      # Core QuickBooks integration logic
│   └── qbo_callback_server.py  # OAuth callback server (production only)
├── docs/                   # Detailed documentation
├── logs/                   # Log files (created automatically)
└── tests/                  # Test suite
```

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is proprietary software owned by 4D EMR.

## Support

For support, please contact the 4D EMR development team.


