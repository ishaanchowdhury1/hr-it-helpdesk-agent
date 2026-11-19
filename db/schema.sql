-- HR/IT Helpdesk demo database (all data is fake)

DROP TABLE IF EXISTS it_tickets;
DROP TABLE IF EXISTS leave_balances;
DROP TABLE IF EXISTS employees;

CREATE TABLE employees (
    employee_id     VARCHAR(10) PRIMARY KEY,
    full_name       VARCHAR(100) NOT NULL,
    department      VARCHAR(50)  NOT NULL,
    designation     VARCHAR(80)  NOT NULL,
    manager_id      VARCHAR(10) REFERENCES employees(employee_id),
    work_email      VARCHAR(120) NOT NULL,
    personal_phone  VARCHAR(20),
    pan_number      VARCHAR(10),
    date_of_joining DATE NOT NULL,
    wfh_eligible    BOOLEAN DEFAULT TRUE
);

CREATE TABLE leave_balances (
    employee_id VARCHAR(10) REFERENCES employees(employee_id),
    year        INT NOT NULL,
    leave_type  VARCHAR(20) NOT NULL CHECK (leave_type IN ('casual','sick','earned')),
    entitled    INT NOT NULL,
    used        INT NOT NULL DEFAULT 0,
    PRIMARY KEY (employee_id, year, leave_type)
);

CREATE TABLE it_tickets (
    ticket_id   VARCHAR(12) PRIMARY KEY,
    employee_id VARCHAR(10) REFERENCES employees(employee_id),
    category    VARCHAR(20) NOT NULL CHECK (category IN ('Access','Network','Hardware','Software')),
    subject     VARCHAR(200) NOT NULL,
    status      VARCHAR(20) NOT NULL CHECK (status IN ('Open','In Progress','Resolved')),
    created_on  DATE NOT NULL
);

INSERT INTO employees VALUES
('E100','Ritika Sen','HR','HR Manager',NULL,'ritika.sen@goaified-demo.in','+91 98300 11111','ABCPS1234K','2021-04-01',TRUE),
('E101','Arjun Mehta','Engineering','Engineering Manager',NULL,'arjun.mehta@goaified-demo.in','+91 98300 22222','BCDPM2345L','2020-07-15',TRUE),
('E102','Priya Nair','Engineering','Software Engineer','E101','priya.nair@goaified-demo.in','+91 98300 33333','CDEPN3456M','2023-01-09',TRUE),
('E103','Rohan Das','Engineering','QA Engineer','E101','rohan.das@goaified-demo.in','+91 98300 44444','DEFPD4567N','2024-06-03',TRUE),
('E104','Sneha Iyer','Sales','Account Executive','E100','sneha.iyer@goaified-demo.in','+91 98300 55555','EFGPI5678P','2025-02-17',FALSE);

INSERT INTO leave_balances VALUES
('E100',2026,'casual',12,5),('E100',2026,'sick',10,2),('E100',2026,'earned',15,8),
('E101',2026,'casual',12,9),('E101',2026,'sick',10,1),('E101',2026,'earned',18,12),
('E102',2026,'casual',12,4),('E102',2026,'sick',10,3),('E102',2026,'earned',15,6),
('E103',2026,'casual',12,12),('E103',2026,'sick',10,0),('E103',2026,'earned',15,2),
('E104',2026,'casual',12,2),('E104',2026,'sick',10,6),('E104',2026,'earned',15,0);

INSERT INTO it_tickets VALUES
('IT-2026-0101','E102','Access','Locked out of HR portal after password change','Resolved','2026-10-28'),
('IT-2026-0114','E102','Hardware','Laptop battery drains in 2 hours','In Progress','2026-11-12'),
('IT-2026-0120','E103','Software','Need Postman installed','Open','2026-11-16'),
('IT-2026-0123','E104','Network','VPN disconnects every 10 minutes','Open','2026-11-18'),
('IT-2026-0125','E101','Hardware','Request for second monitor','Resolved','2026-11-03');
