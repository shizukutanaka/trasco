# Traceo Production Deployment Checklist

Complete this checklist before deploying Traceo to production.

## Security Configuration

### Authentication & Authorization
- [ ] Change default admin password
- [ ] Generate strong JWT secret: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] Set `JWT_SECRET_KEY` in `.env`
- [ ] Enable 2FA/MFA for admin account (if available)
- [ ] Configure RBAC roles and permissions
- [ ] Restrict admin endpoints to specific IP ranges (if behind firewall)

### Database Security
- [ ] Use strong PostgreSQL password (minimum 16 characters)
- [ ] Change default `POSTGRES_PASSWORD` in `.env`
- [ ] Enable PostgreSQL authentication (`pg_hba.conf`)
- [ ] Set `SSL_REQUIRE=true` in PostgreSQL connection
- [ ] Enable database encryption at rest (AWS RDS, Azure Database, etc.)
- [ ] Set up automated database backups
- [ ] Test database restore procedure

### Email/SMTP Security
- [ ] Use app-specific password, not account password (Gmail, etc.)
- [ ] Verify IMAP/SMTP over TLS (ports 993, 587)
- [ ] Store credentials securely (not in version control)
- [ ] Use environment variables or secrets manager
- [ ] Test email sending with valid account

### Network Security
- [ ] Enable HTTPS/TLS for web interface (SSL certificate)
- [ ] Configure CORS properly (not `*` in production)
- [ ] Set up firewall rules
  - [ ] Allow inbound: 443 (HTTPS), 80 (HTTP redirect)
  - [ ] Deny direct access to: 8000 (backend), 5432 (database)
- [ ] Use reverse proxy (Nginx, Apache)
- [ ] Enable HSTS header
- [ ] Set up WAF (Web Application Firewall) rules

### API Security
- [ ] Rate limiting enabled
- [ ] Input validation on all endpoints
- [ ] SQL injection protection (SQLAlchemy ORM handles this)
- [ ] CSRF protection enabled
- [ ] API key authentication for sensitive endpoints
- [ ] Audit logging for all API calls

## Application Configuration

### Environment Variables
- [ ] Copy `.env.example` to `.env`
- [ ] Set `DEBUG=false`
- [ ] Set `LOG_LEVEL=WARNING`
- [ ] Review all settings in `.env`
- [ ] Remove any test/dummy values
- [ ] Verify database connection string
- [ ] Test IMAP connectivity
- [ ] Test SMTP connectivity

### Database Setup
- [ ] Create PostgreSQL database
- [ ] Run database migrations: `alembic upgrade head`
- [ ] Create initial admin user
- [ ] Verify tables created correctly
- [ ] Test database queries work

### Application Setup
- [ ] Install all dependencies: `pip install -r requirements.txt`
- [ ] Collect static files (if using Django/similar)
- [ ] Run database initialization script
- [ ] Verify API endpoints respond
- [ ] Test email ingestion
- [ ] Test report sending

## Deployment Platform

### Recommended Options
- [ ] AWS (ECS/Fargate, RDS, ALB)
- [ ] Google Cloud (Cloud Run, Cloud SQL, Cloud Load Balancer)
- [ ] Azure (Container Instances, Azure Database, Application Gateway)
- [ ] DigitalOcean (App Platform, Managed Database)
- [ ] Heroku (simple, great for testing)

### Infrastructure as Code
- [ ] Create Terraform/CloudFormation templates
- [ ] Document infrastructure setup
- [ ] Set up CI/CD pipeline
- [ ] Automate deployments
- [ ] Version all infrastructure code

## Monitoring & Logging

### Application Monitoring
- [ ] Set up application performance monitoring (APM)
  - [ ] Datadog
  - [ ] New Relic
  - [ ] AWS CloudWatch
  - [ ] Google Cloud Monitoring
- [ ] Configure error tracking (Sentry, etc.)
- [ ] Set up uptime monitoring
- [ ] Create alerts for:
  - [ ] High error rate
  - [ ] Slow response times
  - [ ] Database connection failures
  - [ ] IMAP/SMTP failures
  - [ ] Disk space low

### Logging
- [ ] Configure centralized logging
  - [ ] ELK Stack
  - [ ] Splunk
  - [ ] Datadog
  - [ ] AWS CloudWatch
  - [ ] Google Cloud Logging
- [ ] Set log retention policy (30-90 days recommended)
- [ ] Encrypt logs in transit and at rest
- [ ] Test log searching and filtering
- [ ] Create dashboards for key metrics

### Health Checks
- [ ] Set up health check endpoints
- [ ] Configure load balancer health checks
- [ ] Monitor database health
- [ ] Monitor API response times
- [ ] Set up synthetic monitoring

## Backup & Disaster Recovery

### Backup Strategy
- [ ] Configure automatic daily backups
- [ ] Test backup restore procedure
- [ ] Store backups in separate location
- [ ] Encrypt backups
- [ ] Verify backup integrity
- [ ] Document backup schedule and retention

### Disaster Recovery
- [ ] Create disaster recovery plan
- [ ] Test failover procedure
- [ ] Document recovery time objectives (RTO)
- [ ] Document recovery point objectives (RPO)
- [ ] Set up high availability (if required)
- [ ] Configure replication/redundancy

## Performance Optimization

### Database Optimization
- [ ] Create indexes on frequently queried columns
- [ ] Analyze query performance
- [ ] Set up query caching where appropriate
- [ ] Configure connection pooling
- [ ] Monitor database performance

### Application Optimization
- [ ] Enable gzip compression
- [ ] Enable caching (Redis, Memcached)
- [ ] Optimize API response times
- [ ] Use CDN for static assets
- [ ] Monitor CPU/memory usage
- [ ] Configure auto-scaling if needed

### Load Testing
- [ ] Perform load testing with expected traffic
- [ ] Identify bottlenecks
- [ ] Optimize slow endpoints
- [ ] Verify database can handle concurrent connections
- [ ] Test IMAP/SMTP rate limits

## Documentation & Knowledge

### Documentation
- [ ] Document deployment procedure
- [ ] Document configuration settings
- [ ] Document backup/restore procedure
- [ ] Document incident response procedures
- [ ] Document escalation contacts
- [ ] Create runbooks for common issues

### Team Knowledge
- [ ] Train operations team
- [ ] Create on-call rotation
- [ ] Document troubleshooting steps
- [ ] Record screen captures of deployment
- [ ] Document known issues and workarounds

## Testing

### Pre-Deployment Testing
- [ ] Run full test suite: `pytest tests/ --cov`
- [ ] Verify all tests pass
- [ ] Test in staging environment
- [ ] Perform security testing (OWASP top 10)
- [ ] Perform load testing
- [ ] Test database backup/restore
- [ ] Test SSL certificate installation

### Post-Deployment Testing
- [ ] Verify all endpoints are accessible
- [ ] Test email ingestion end-to-end
- [ ] Test report sending end-to-end
- [ ] Test dashboard functionality
- [ ] Verify logging is working
- [ ] Check monitoring/alerting

## Compliance & Audit

### Data Protection
- [ ] Comply with GDPR (if handling EU data)
- [ ] Comply with CCPA (if handling CA data)
- [ ] Implement data retention policies
- [ ] Enable data deletion/export features
- [ ] Document data handling practices

### Audit Trail
- [ ] Enable audit logging for sensitive operations
- [ ] Log user authentication events
- [ ] Log report submissions
- [ ] Log administrative actions
- [ ] Monitor for suspicious activity

### Security Audits
- [ ] Perform penetration testing
- [ ] Conduct security code review
- [ ] Scan for vulnerabilities (OWASP, CVE)
- [ ] Verify no hardcoded secrets
- [ ] Check for outdated dependencies

## Final Checks

### Deployment Day
- [ ] Schedule maintenance window (if downtime expected)
- [ ] Notify users of deployment
- [ ] Have rollback plan ready
- [ ] Have team on standby
- [ ] Monitor closely after deployment
- [ ] Be ready to rollback if issues

### Post-Deployment
- [ ] Monitor error rates
- [ ] Check performance metrics
- [ ] Verify all features working
- [ ] Confirm backup is working
- [ ] Document any issues encountered
- [ ] Send deployment completion notification

## Sign-Off

- Deployment Lead: _________________ Date: _______
- Operations Manager: ______________ Date: _______
- Security Manager: ______________ Date: _______

## Notes

Use this space to document any issues or special considerations:

```
[Notes here]
```
