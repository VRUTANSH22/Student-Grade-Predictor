# Deployment Guide — Student Performance Predictor

## Prerequisites

- Python 3.10+
- pip / venv
- (Production) MySQL 8.0+
- (Production) Linux server with systemd

---

## Local Development Setup

```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
source venv/bin/activate       # Linux/macOS

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and edit environment file
cp .env.example .env
# Default settings use SQLite — no database installation needed

# 4. Train ML models (generates .pkl files in models/)
python train_models.py

# 5. Start development server
python app.py
# → http://localhost:5000
# → http://localhost:5000/apidocs  (Swagger UI)
```

---

## MySQL Production Setup

### 1. Install MySQL 8.0+

```bash
# Ubuntu/Debian
sudo apt update && sudo apt install mysql-server -y
sudo systemctl start mysql
sudo mysql_secure_installation
```

### 2. Create database and user

```sql
-- Connect as root
mysql -u root -p

CREATE DATABASE student_predictor
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

CREATE USER 'gradeai'@'localhost' IDENTIFIED BY 'strong-password-here';
GRANT ALL PRIVILEGES ON student_predictor.* TO 'gradeai'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

### 3. Import schema

```bash
mysql -u gradeai -p student_predictor < database/schema.sql
```

### 4. Update `.env`

```
USE_SQLITE=false
DB_HOST=localhost
DB_PORT=3306
DB_NAME=student_predictor
DB_USER=gradeai
DB_PASSWORD=strong-password-here
FLASK_ENV=production
SECRET_KEY=<generate-with-python-secrets-module>
```

Generate a secret key:
```python
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Gunicorn Production Server

### Run manually

```bash
gunicorn \
  --workers 4 \
  --threads 2 \
  --bind 0.0.0.0:5000 \
  --timeout 120 \
  --access-logfile logs/gunicorn-access.log \
  --error-logfile  logs/gunicorn-error.log \
  app:app
```

**Worker count rule of thumb:** `workers = (2 × CPU cores) + 1`

---

## systemd Service (Auto-restart on Boot)

Create `/etc/systemd/system/gradeai.service`:

```ini
[Unit]
Description=GradeAI — Student Performance Predictor
After=network.target mysql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/student_performance_predictor
Environment="PATH=/opt/student_performance_predictor/venv/bin"
ExecStart=/opt/student_performance_predictor/venv/bin/gunicorn \
    --workers 4 \
    --bind 0.0.0.0:5000 \
    --timeout 120 \
    app:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable gradeai
sudo systemctl start  gradeai
sudo systemctl status gradeai
```

---

## Nginx Reverse Proxy (Optional)

Create `/etc/nginx/sites-available/gradeai`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host             $host;
        proxy_set_header   X-Real-IP        $remote_addr;
        proxy_set_header   X-Forwarded-For  $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    location /static/ {
        alias /opt/student_performance_predictor/static/;
        expires 7d;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/gradeai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## Log Rotation

```bash
# View today's structured log
tail -f logs/app.json | python -m json.tool

# View all log entries for a student
grep '"student_id": "STU001"' logs/app.json

# Count prediction errors today
grep '"status": "error"' logs/app.json | wc -l
```

---

## Database Backup

```bash
# Full backup
mysqldump -u gradeai -p student_predictor > backup_$(date +%Y%m%d).sql

# Automated daily backup (cron)
# Add to crontab: crontab -e
0 2 * * * mysqldump -u gradeai -p'password' student_predictor > /backups/student_predictor_$(date +\%Y\%m\%d).sql

# Restore from backup
mysql -u gradeai -p student_predictor < backup_20260612.sql
```

---

## Health Monitoring

```bash
# Quick health check
curl http://localhost:5000/api/health

# Watch stats every 5 seconds
watch -n5 'curl -s http://localhost:5000/api/stats | python -m json.tool'

# Check service status
sudo systemctl status gradeai
journalctl -u gradeai -f   # tail service logs
```

---

## Performance Benchmarks

Run using Apache Bench (ab):

```bash
# Single endpoint benchmark (100 requests, 10 concurrent)
ab -n 100 -c 10 http://localhost:5000/api/health

# POST prediction benchmark (requires ab with POST body file)
echo '{"student_id":"BENCH","student_name":"Test","attendance_percentage":85,"study_hours_per_week":15,"assignment_score":78,"quiz_marks":82,"previous_gpa":3.5}' > /tmp/body.json
ab -n 100 -c 10 -p /tmp/body.json -T application/json http://localhost:5000/api/predict
```

Target: **< 100ms p99** for `/api/predict` on local hardware.
