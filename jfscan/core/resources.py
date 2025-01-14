#!/usr/bin/env python3
import logging
import tldextract
import sqlite3
import validators


class Resources:
    def __init__(self, utils):
        self.logger = logging.getLogger(__name__)
        self.cidrs = []
        self.utils = utils
        self.conn = None

        try:
            self.conn = sqlite3.connect(":memory:")
        except Exception as e:
            self.logger.fatal("%s could not create database", bin)

            raise SystemExit

        cur = self.conn.cursor()

        init_table_domains = "CREATE TABLE domains\
             (domain TEXT, ip_rowid INTEGER, UNIQUE(domain, ip_rowid))"
        init_table_ips = "CREATE TABLE ips\
             (ip TEXT, version INTEGER, UNIQUE(ip, version))"
        init_table_ports = "CREATE TABLE ports\
             (port INTEGER, protocol TEXT, ip_rowid INTEGER, UNIQUE(port, protocol, ip_rowid))"
        init_table_cidrs = "CREATE TABLE cidrs\
             (cidr TEXT, version, UNIQUE(cidr, version))"

        cur.execute(init_table_domains)
        cur.execute(init_table_ips)
        cur.execute(init_table_ports)
        cur.execute(init_table_cidrs)

        self.conn.commit()

    def add_cidr(self, cidr):
        conn = self.conn
        cur = conn.cursor()

        cur.execute(
            "INSERT OR IGNORE INTO cidrs(cidr, version) VALUES(?, ?)", (cidr, 4)
        )

        conn.commit()

    def add_domain(self, domain):
        ips = self.utils.resolve_host(domain)

        conn = self.conn
        cur = conn.cursor()

        if ips is None or len(ips) == 0:
            query = "INSERT OR IGNORE INTO domains(domain) VALUES(?)"
            cur.execute(query, (domain,))
            conn.commit()

            return

        for ip in ips:
            insert_ip = "INSERT OR IGNORE INTO ips(ip, version) VALUES(?, ?)"

            if validators.ipv4(ip):
                cur.execute(insert_ip, (ip, 4))
            elif validators.ipv6(ip):
                cur.execute(insert_ip, (ip, 6))
            else:
                continue

            cur.execute(
                "INSERT OR IGNORE INTO\
                 domains(domain, ip_rowid) \
                     VALUES(?, (SELECT rowid FROM ips where ip = ?))",
                (domain, ip),
            )

        conn.commit()

    def add_ip(self, ip):
        conn = self.conn
        cur = conn.cursor()

        query = "INSERT OR IGNORE INTO ips(ip, version) VALUES(?, ?)"

        if validators.ipv4(ip):
            cur.execute(query, (ip, 4))

        if validators.ipv6(ip):
            cur.execute(query, (ip, 6))

        conn.commit()

    def add_port(self, ip, port, protocol):
        conn = self.conn
        cur = conn.cursor()

        self.add_ip(ip)

        cur.execute(
            "INSERT OR IGNORE INTO\
             ports(port, protocol, ip_rowid)\
                  VALUES(?, ?, (SELECT rowid FROM ips WHERE ip = ?))",
            (port, protocol, ip),
        )

        conn.commit()

    def get_ips(self):
        conn = self.conn
        cur = conn.cursor()

        ips = cur.execute("SELECT DISTINCT ip FROM ips").fetchall()

        return ips

    def get_domains_ips_and_ports(self):
        conn = self.conn
        cur = conn.cursor()

        ips = cur.execute("SELECT DISTINCT ip FROM ips").fetchall()

        results = []

        for ip in ips:
            ip = ip[0]

            ports = cur.execute(
                "SELECT port FROM ports JOIN ips ON\
                 ip = ips.ip WHERE ips.rowid = ports.ip_rowid AND ip = ?",
                (ip,),
            ).fetchall()

            if len(ports) == 0:
                continue

            domains = cur.execute(
                "SELECT domain FROM domains\
                 WHERE ip_rowid = (SELECT rowid FROM ips WHERE ip = ?)",
                (ip,),
            ).fetchall()

            if len(domains) != 0:
                results.append(
                    ([domain for domain, in domains], ip, [port for port, in ports])
                )
            else:
                results.append(([], ip, [port for port, in ports]))

        return results

    def get_cidrs(self):
        conn = self.conn
        cur = conn.cursor()

        cidrs = cur.execute("SELECT DISTINCT cidr FROM cidrs").fetchall()

        return cidrs

    def get_root_domains(self):
        conn = self.conn
        cur = conn.cursor()

        domains = cur.execute("SELECT DISTINCT domain FROM domains").fetchall()

        root_domains = []

        for (domain,) in domains:
            try:
                parse = (
                    tldextract.extract(domain).domain
                    + "."
                    + tldextract.extract(domain).suffix
                )
            except:
                continue

            root_domains.append(parse)

        return list(set(root_domains))

    def get_all_domains(self):
        conn = self.conn

        cur = conn.cursor()

        domains = cur.execute("SELECT DISTINCT domain FROM domains").fetchall()

        return domains

    def get_list(self, ips=False, domains=False):
        conn = self.conn
        cur = conn.cursor()
        results = []

        if ips is True:
            rows = cur.execute(
                "SELECT DISTINCT ip, port FROM ports\
                 JOIN ips ON ip = ips.ip WHERE ips.rowid = ports.ip_rowid"
            ).fetchall()
            for row in rows:
                results.append(f"{row[0]}:{row[1]}")

        if domains is True:
            rows = cur.execute(
                "SELECT DISTINCT domain, port FROM ports\
                 JOIN domains ON domain = domains.domain WHERE domains.ip_rowid = ports.ip_rowid"
            ).fetchall()
            for row in rows:
                results.append(f"{row[0]}:{row[1]}")

        return results

    def count_ips(self):
        conn = self.conn
        cur = conn.cursor()

        cidrs = cur.execute("SELECT DISTINCT cidr FROM cidrs").fetchall()

        address_count = 0

        for (cidr,) in cidrs:
            address_count += (2 ** (32 - int(cidr.split("/")[1]))) - 2

        ips_count = cur.execute("SELECT count(DISTINCT ip) FROM ips").fetchall()

        address_count += ips_count[0][0]

        return address_count

    def count_ports(self):
        conn = self.conn
        cur = conn.cursor()

        port_count = cur.execute("SELECT count(*) FROM ports").fetchall()

        return port_count[0][0]

    def count_alive_ips(self):
        conn = self.conn
        cur = conn.cursor()

        port_count = cur.execute("SELECT count(DISTINCT ip_rowid) FROM ports").fetchall()

        return port_count[0][0]
