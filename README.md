# Office NFC Tally Payments 🥤

A lightweight, self-hosted fridge drink tally web application designed for Raspberry Pi 5 with Docker and SQLite. Perfect for tracking office beverage consumption with simple NFC tap functionality.

## Features ✨

- **NFC Tap Integration**: One NTAG215 NFC tag opens `/tap` endpoint for instant drink logging
- **Smart Authentication**: 
  - Instant drink increment for logged-in users (long-lived secure cookie)
  - User selection + PIN login with "remember me" option for first-time users
- **User Management**: Admin can create users and set PINs
- **Flexible Pricing**: Admin-configurable price per drink
- **Billing Periods**: Manually close billing periods to generate reports
- **Comprehensive Reports**: Per-user totals and stock summary for each period
- **Mobile-Friendly**: Responsive design works on phones, tablets, and desktops
- **Docker Ready**: Complete Docker and docker-compose setup for easy deployment

## Quick Start 🚀

### Prerequisites

- Raspberry Pi 5 (or any Linux system with Docker support)
- Docker and Docker Compose installed
- NTAG215 NFC tags (optional, but recommended)

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/PTA-Wine-Step-Mom/Office-NFC-Tally-Payments.git
   cd Office-NFC-Tally-Payments
   ```

2. **Configure environment** (optional but recommended):
   ```bash
   cp .env.example .env
   # Edit .env and set a secure SECRET_KEY
   # Generate one with: python -c "import secrets; print(secrets.token_hex(32))"
   ```

3. **Build and run with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

4. **Access the application**:
   - Open your browser and navigate to `http://localhost:5000`
   - Or use your Raspberry Pi's IP address: `http://192.168.1.xxx:5000`

5. **Login as admin**:
   - Default credentials: `admin` / `0000`
   - **⚠️ Change the default PIN immediately!**

### Manual Installation (without Docker)

1. **Install dependencies**:
   ```bash
   cd Office-NFC-Tally-Payments
   pip install -r requirements.txt
   ```

2. **Initialize database and run**:
   ```bash
   cd app
   python database.py  # Initialize database
   python app.py       # Run the application
   ```

3. **Access at** `http://localhost:5000`

## Usage Guide 📖

### For Users

1. **First Time Setup**:
   - Tap NFC tag or navigate to `/tap`
   - Select your name from the dropdown
   - Enter your PIN
   - Check "Remember me" to stay logged in
   - Tap "Add Drink"

2. **Subsequent Taps** (when logged in):
   - Simply tap the NFC tag
   - Your drink is logged instantly!
   - See your updated count and total

3. **View Your Stats**:
   - Go to the home page to see your drink count and cost for the current period

### For Administrators

1. **Admin Dashboard** (`/admin`):
   - View current billing period statistics
   - See per-user consumption breakdown
   - Manage users

2. **Add Users**:
   - Navigate to Admin → Add User
   - Enter name and 4-6 digit PIN
   - Optionally grant admin privileges

3. **Manage Pricing**:
   - Go to Settings
   - Update "Default Price per Drink"
   - Applies to current and future periods

4. **Close Billing Period**:
   - From Admin Dashboard, click "Close Period & Generate Report"
   - System generates detailed report with per-user totals
   - New billing period starts automatically

5. **View Reports**:
   - Access billing history to view all periods
   - View detailed reports with per-user breakdown
   - Print reports for record-keeping

## NFC Setup 🏷️

### Hardware Requirements

- **NFC Reader/Writer**: Compatible with NTAG215 tags
- **NTAG215 NFC Tags**: Available on Amazon, eBay, etc.

### Programming the NFC Tag

1. **Simple Redirect Method** (recommended):
   - Use an NFC writing app (like NFC Tools for Android/iOS)
   - Write a URL record: `http://your-pi-ip:5000/tap`
   - When tapped, phone opens the /tap page automatically

2. **Advanced Method** (for dedicated NFC readers):
   - If using a dedicated NFC reader connected to Raspberry Pi
   - Configure reader to trigger HTTP request to `/tap` endpoint
   - Can integrate with home automation systems

### Example Configuration

For a Raspberry Pi at `192.168.1.100`:
- Program NFC tag with URL: `http://192.168.1.100:5000/tap`
- Users tap phone on tag → browser opens → instant drink logging

## Architecture 🏗️

### Technology Stack

- **Backend**: Python Flask (lightweight web framework)
- **Database**: SQLite (file-based, no server required)
- **Frontend**: HTML5, CSS3, vanilla JavaScript
- **Deployment**: Docker + Docker Compose
- **Target Platform**: Raspberry Pi 5 (ARM64)

### Database Schema

- **users**: User information (name, PIN, admin flag)
- **drinks**: Individual drink records with timestamps
- **billing_periods**: Track billing cycles with start/end dates and pricing
- **settings**: Application configuration (default pricing, etc.)

### Security Features

- Secure session cookies with configurable expiration
- PIN-based authentication
- Password fields use proper input types
- CSRF protection via Flask
- No sensitive data in URLs or logs

## Configuration ⚙️

### Environment Variables

- `SECRET_KEY`: Flask secret key for session encryption (required in production)
- `FLASK_ENV`: Set to `production` for deployment

### Docker Volumes

- `./data`: Persists SQLite database across container restarts
- `drink-db`: Named volume for database file

### Port Configuration

Default port is `5000`. To change:

```yaml
# docker-compose.yml
ports:
  - "8080:5000"  # External:Internal
```

## Troubleshooting 🔧

### Database Issues

If database gets corrupted:
```bash
# Stop container
docker-compose down

# Backup current database
cp data/drinks_tally.db data/drinks_tally.db.backup

# Remove and reinitialize
rm data/drinks_tally.db
docker-compose up -d
```

### Container Won't Start

Check logs:
```bash
docker-compose logs -f
```

Rebuild container:
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Windows Line Ending Issues

**Symptoms**: Container fails to start with errors like:
- `: not found`
- `python: can't open file '/app/app.py\r'`

**Cause**: Git on Windows may convert Unix line endings (LF) to Windows line endings (CRLF), causing shell scripts to fail in Linux containers.

**Solution**: This is now automatically fixed by:
1. `.gitattributes` file enforces LF endings for shell scripts
2. Dockerfile converts any CRLF to LF during build

**Manual fix** (if needed):
```bash
# On Windows, before building:
git config core.autocrlf false
git rm --cached -r .
git reset --hard

# Or manually convert the file:
dos2unix app/start.sh  # If you have dos2unix installed
# Or in Git Bash:
sed -i 's/\r$//' app/start.sh
```

Then rebuild the Docker image:
```bash
docker-compose build --no-cache
docker-compose up -d
```

### Can't Access from Other Devices

1. Check firewall settings on Raspberry Pi:
   ```bash
   sudo ufw allow 5000/tcp
   ```

2. Verify container is listening on all interfaces:
   ```bash
   docker-compose ps
   ```

3. Find Raspberry Pi IP address:
   ```bash
   hostname -I
   ```

## Development 💻

### Running in Development Mode

```bash
cd app
export FLASK_ENV=development
python app.py
```

### Project Structure

```
Office-NFC-Tally-Payments/
├── app/
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── tap_*.html
│   │   ├── admin_*.html
│   │   └── ...
│   ├── app.py              # Main Flask application
│   ├── database.py         # Database initialization
│   └── db_utils.py         # Database utilities
├── data/                   # SQLite database (generated)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Contributing 🤝

Contributions are welcome! Please feel free to submit a Pull Request.

## License 📄

This project is open source and available under the MIT License.

## Support 💬

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions

## Roadmap 🗺️

Future enhancements planned:
- [ ] Email/SMS notifications for billing period closure
- [ ] Export reports to CSV/PDF
- [ ] Multi-currency support
- [ ] Dark mode theme
- [ ] API endpoints for integration
- [ ] Mobile app companion
- [ ] Stock level warnings
- [ ] QR code alternative to NFC

## Acknowledgments 🙏

Built with ❤️ for office beverage management. Inspired by the need for simple, effective drink tracking without complex infrastructure.

---

**Note**: This is designed for trusted environments (office). For public-facing deployments, implement additional security measures (HTTPS, rate limiting, stronger authentication).
