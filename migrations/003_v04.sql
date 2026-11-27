ALTER TABLE complaints ADD COLUMN phash TEXT;
ALTER TABLE complaints ADD COLUMN duplicate_probability REAL;
INSERT INTO authorities(name,type,state,district,city,categories,grievance_url,grievance_email,helpline,verified,last_verified,source_url) VALUES
 ('Pune Municipal Corporation (PMC CARE grievance registration)','grievance','maharashtra','pune','pune','garbage,drainage,toilet,road,water,electricity','https://pmccare.in/cep/home',NULL,NULL,1,'2026-11-27','https://webadmin.pmc.gov.in/citizen-services'),
 ('Maharashtra Public Grievance Portal (CM Office)','escalation','maharashtra',NULL,NULL,NULL,'https://grievances.maharashtra.gov.in/en',NULL,'1800 120 8040 (toll free)',1,'2026-11-27','https://grievances.maharashtra.gov.in/en'),
 ('Gaya Municipal Corporation','grievance','bihar','gaya','gaya','garbage,drainage,toilet,road,water,electricity','https://gayamunicipal.net/pmc/public/index.html',NULL,'1800 121 8545',1,'2026-11-27','https://gayamunicipal.net/pmc/public/index.html');
