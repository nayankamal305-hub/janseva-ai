# API (JSON, Bearer token)
Public: GET /api/health /api/emergency /api/platforms /api/authorities /api/representatives /api/assistant?q=&lang= /api/public/feed|stats|heatmap (filters: state, city, category, status, severity, days, from, to, department) /api/public/report?month=YYYY-MM&format=csv
Auth: POST /api/otp/request {phone}; POST /api/otp/verify {phone,code,name}; POST /api/register (dev only)
Citizen: POST /api/upload (raw JPEG/PNG body); POST /api/complaints; GET /api/complaints; GET /api/complaints/{id}[/route|/letter]; POST /api/complaints/{id}/confirm|submit|reference|sync|verify|support; POST /api/account/delete
Admin (role-scoped): GET /api/admin/me|complaints|verification-queue|report; super admin: control-center, analytics, escalations, escalation-policy, audit, integration-log, notifications, admins, duplicates, health; POST /api/admin/complaints/{id}/reroute|approve-photo, authorities, platforms, representatives, admins, sync, run-escalation, escalation-policy
