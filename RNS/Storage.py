# Reticulum License
#
# Copyright (c) 2016-2026 Mark Qvist
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# - The Software shall not be used in any kind of system which includes amongst
#   its functions the ability to purposefully do harm to human beings.
#
# - The Software shall not be used, directly or indirectly, in the creation of
#   an artificial intelligence, machine learning or language model training
#   dataset, including but not limited to any use that contributes to the
#   training or development of such a model or algorithm.
#
# - The above copyright notice and this permission notice shall be included in
#   all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import RNS
import hashlib
import threading
import os
import time
from array import array

class AnnounceRateTable:
    # Columnar store for announce rate tracking. Layout:
    #   _index  : dict[destination_hash -> slot]
    #   _keys   : list[slot] -> destination_hash (for swap-remove bookkeeping)
    #   _last   : array('d')  last non-violating announce time
    #   _blocked: array('d')  blocked_until
    #   _viol   : array('i')  rate_violations
    #   _ts     : array('d')  flat ring of max_timestamps doubles per slot
    #   _ts_len : array('B')  valid timestamp count per slot
    #   _ts_head: array('B')  ring write cursor per slot

    def __init__(self, max_timestamps=16):
        assert max_timestamps <= 255, "Timestamp ring size must fit in a single byte"
        self.max_ts   = max_timestamps
        self._index   = {}
        self._keys    = []
        self._last    = array('d')
        self._blocked = array('d')
        self._viol    = array('i')
        self._ts      = array('d')
        self._ts_len  = array('B')
        self._ts_head = array('B')
        self._cursor  = 0

    def __len__(self):                        return len(self._keys)
    def __contains__(self, destination_hash): return destination_hash in self._index

    # Perform the announce-rate check-and-update for one announce.
    # Caller must hold the announce_rate_table_lock.
    def check_and_update(self, destination_hash, now, target, grace, penalty):
        slot = self._index.get(destination_hash)

        if slot is None:
            slot = len(self._keys)
            self._index[destination_hash] = slot
            self._keys.append(destination_hash)
            self._last.append(now)
            self._blocked.append(0.0)
            self._viol.append(0)
            self._ts.extend([0.0]*self.max_ts)
            self._ts[slot*self.max_ts] = now
            self._ts_len.append(1)
            self._ts_head.append(1 % self.max_ts)
            return False

        base = slot*self.max_ts
        head = self._ts_head[slot]
        self._ts[base+head] = now
        self._ts_head[slot] = (head+1) % self.max_ts
        if self._ts_len[slot] < self.max_ts: self._ts_len[slot] += 1

        current_rate = now - self._last[slot]
        rate_blocked = False

        if now > self._blocked[slot]:
            if current_rate < target: self._viol[slot] += 1
            else:
                v = self._viol[slot] - 1
                self._viol[slot] = v if v > 0 else 0

            if self._viol[slot] > grace:
                self._blocked[slot] = self._last[slot] + target + penalty
                rate_blocked = True
            else: self._last[slot] = now

        else: rate_blocked = True

        return rate_blocked

    # Caller must hold the table lock
    def cull(self, now, ttl, max_scan=1024, max_cull=None):
        if max_cull is None: max_cull = max_scan
        horizon = now - ttl
        culled  = 0
        scanned = 0
        n = len(self._keys)

        while scanned < max_scan and culled < max_cull and n > 0:
            if self._cursor >= n: self._cursor = 0
            slot = self._cursor

            if self._last[slot] < horizon and self._blocked[slot] <= now:
                last_i = n - 1
                stale_key = self._keys[slot]

                if slot != last_i:
                    moved_key              = self._keys[last_i]
                    self._keys[slot]       = moved_key
                    self._index[moved_key] = slot
                    self._last[slot]       = self._last[last_i]
                    self._blocked[slot]    = self._blocked[last_i]
                    self._viol[slot]       = self._viol[last_i]
                    self._ts_len[slot]     = self._ts_len[last_i]
                    self._ts_head[slot]    = self._ts_head[last_i]

                    f = last_i*self.max_ts; t = slot*self.max_ts
                    self._ts[t:t+self.max_ts] = self._ts[f:f+self.max_ts]

                self._keys.pop()
                self._last.pop(); self._blocked.pop(); self._viol.pop()
                self._ts_len.pop(); self._ts_head.pop()
                del self._ts[len(self._ts)-self.max_ts:]  # drop tail block of removed slot
                del self._index[stale_key]

                n -= 1
                culled += 1
                # Do not advance cursor, re-examine the slot a moved entry landed in

            else:
                self._cursor = slot + 1
                scanned += 1

        if self._cursor >= n: self._cursor = 0

        return culled

    # Hold table lock, or accept a possibly inconsistent snapshot
    def items(self):
        for slot, key in enumerate(self._keys):
            n    = self._ts_len[slot]
            head = self._ts_head[slot]
            base = slot*self.max_ts
            if n < self.max_ts: ts = list(self._ts[base:base+n])
            else:               ts = list(self._ts[base+head:base+self.max_ts]) + list(self._ts[base:base+head])
            yield key, { "last": self._last[slot], "rate_violations": self._viol[slot],
                         "blocked_until": self._blocked[slot], "timestamps": ts }

class PacketHashlist:
    # Bucketed byte-blob packet filter hashlist, with the primary
    # design goal of memory coherence and density. All operations
    # are safe to call without holding a lock.

    def __init__(self, hash_width=32, bucket_count=16384):
        assert bucket_count > 0 and bucket_count & (bucket_count-1) == 0, "Bucket count must be a power of two"
        self.width   = hash_width
        self._nb     = bucket_count
        self._mask   = bucket_count - 1
        self._cur    = [bytearray() for _ in range(bucket_count)]
        self._prv    = [bytearray() for _ in range(bucket_count)]
        self._count  = 0

    def __len__(self):
        return self._count

    def __contains__(self, packet_hash):
        bucket = (packet_hash[0] | (packet_hash[1] << 8)) & self._mask
        return packet_hash in self._cur[bucket] or packet_hash in self._prv[bucket]

    def add(self, packet_hash):
        assert len(packet_hash) == self.width, "Packet hash width mismatch"
        bucket = (packet_hash[0] | (packet_hash[1] << 8)) & self._mask
        if packet_hash not in self._cur[bucket]:
            self._cur[bucket].extend(packet_hash)
            self._count += 1

    def discard(self, packet_hash):
        w = self.width
        bucket = (packet_hash[0] | (packet_hash[1] << 8)) & self._mask
        for generation in (self._cur, self._prv):
            entries = generation[bucket]
            pos = entries.find(packet_hash)
            while pos != -1:
                if pos % w == 0:
                    del entries[pos:pos+w]
                    if generation is self._cur: self._count -= 1
                    pos = entries.find(packet_hash, pos)
                else:
                    pos = entries.find(packet_hash, pos+1)

    def swap(self):
        self._prv = self._cur
        self._cur = [bytearray() for _ in range(self._nb)]
        self._count = 0

    # Current-generation buckets for persist operations
    def buckets(self): return tuple(self._cur)

class KnownDestinationsStore:
    # Write-behind SQLite storage backend for known destinations.
    # The actual in-memory table is used directly for all transport
    # operations; this serves purely as the store, and no read operations
    # utilize the database directly.

    def __init__(self, db_path, hash_width=16, read_only=False):
        import sqlite3
        self.sqlite3             = sqlite3
        self.db_path             = db_path
        self.hash_width          = hash_width
        self.read_only           = read_only
        self._dirty_upsert       = set()
        self._dirty_delete       = set()
        self._ratchet_upserts    = {}
        self._ratchet_deletes    = set()
        self._kd_quarantine      = {}
        self._ratchet_quarantine = {}
        self._flush_lock         = threading.Lock()

        if read_only: self._conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False, isolation_level=None)
        else:
            self._conn = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA journal_size_limit=8388608")
            self.__create_schema()

    def close(self):
        if self._conn != None:
            self._conn.close()
            self._conn = None

    def __create_schema(self):
        db_version = self._conn.execute("PRAGMA user_version").fetchone()[0]

        self._conn.execute("""CREATE TABLE IF NOT EXISTS known_destinations (
            destination_hash BLOB PRIMARY KEY,
            last_heard       REAL NOT NULL,
            packet_hash      BLOB,
            public_key       BLOB NOT NULL,
            app_data         BLOB,
            used             REAL NOT NULL DEFAULT 0,
            stamp            BLOB,
            stamp_value      REAL,
            lr_cost          REAL,
            identity_hash    BLOB NOT NULL)""")

        self._conn.execute("""CREATE TABLE IF NOT EXISTS ratchets (
            destination_hash BLOB PRIMARY KEY,
            ratchet          BLOB NOT NULL,
            received         REAL NOT NULL)""")

        # Pre-release migrations
        # Will be folded into finalized schema before 1.6.0 release
        try:
            self._conn.execute("BEGIN")
            if 0 < db_version < 2: self._conn.execute("ALTER TABLE known_destinations ADD COLUMN lr_cost REAL")
            if 0 < db_version < 3: self._conn.execute("ALTER TABLE known_destinations ALTER COLUMN packet_hash DROP NOT NULL")
            self._conn.execute("PRAGMA user_version = 3")
            self._conn.execute("COMMIT")
            self._conn.commit()

        except Exception as e:
            RNS.log(f"Pre-release database migration failed: {e}", RNS.LOG_CRITICAL)
            RNS.log(f"You will need to remove the known_destinations.db* files from your storage directory", RNS.LOG_CRITICAL)
            RNS.log(f"On the next instance start, the database will be rebuilt", RNS.LOG_CRITICAL)
            RNS.log(f"Exiting now", RNS.LOG_CRITICAL)
            time.sleep(1)
            RNS.panic()

    def __entry_row(self, destination_hash, entry):
        stamp         = entry[5] if len(entry) > 5 else None
        stamp_value   = entry[6] if len(entry) > 6 else 0
        lr_cost       = entry[7] if len(entry) > 7 else None
        identity_hash = hashlib.sha256(entry[2]).digest()[:self.hash_width]
        return (destination_hash, entry[0], entry[1], entry[2], entry[3], entry[4], stamp, stamp_value, lr_cost, identity_hash)

    # Caller must hold Identity.known_destinations_lock
    def mark_dirty(self, destination_hash):
        if self.read_only: return
        self._dirty_delete.discard(destination_hash)
        self._kd_quarantine.pop(destination_hash, None)
        self._dirty_upsert.add(destination_hash)

    # Caller must hold Identity.known_destinations_lock
    def mark_deleted(self, destination_hash):
        if self.read_only: return
        self._dirty_upsert.discard(destination_hash)
        self._dirty_delete.add(destination_hash)
        self._kd_quarantine.pop(destination_hash, None)
        self._ratchet_quarantine.pop(destination_hash, None)

    # Caller must hold Identity.known_destinations_lock
    def take_pending(self):
        if self.read_only: return set(), set(), {}, set()
        upserts               = self._dirty_upsert
        deletes               = self._dirty_delete
        ratchet_upserts       = self._ratchet_upserts
        ratchet_deletes       = self._ratchet_deletes
        self._dirty_upsert    = set()
        self._dirty_delete    = set()
        self._ratchet_upserts = {}
        self._ratchet_deletes = set()
        return upserts, deletes, ratchet_upserts, ratchet_deletes

    # Caller must hold the flush lock and have an already open transaction
    def __wrap_exec(self, sql, rows):
        rejects = []

        # By default, run batched queries in chunks.
        for i in range(0, len(rows), 4096):
            chunk = rows[i:i+4096]
            try:
                self._conn.execute("SAVEPOINT chunk")
                self._conn.executemany(sql, chunk)
                self._conn.execute("RELEASE chunk")

            # But on integrity and data errors, roll back the chunk
            # and iterate per-row, so we can catch any violating
            # entries and quarantine them. A later, sane update
            # will then unquarantine and heal upon arrival.
            #
            # Other exceptions are intentionally not caught here,
            # so they can propagate directly.
            except (self.sqlite3.IntegrityError, self.sqlite3.DataError):
                self._conn.execute("ROLLBACK TO chunk")
                for row in chunk:
                    try:
                        self._conn.execute("SAVEPOINT row")
                        self._conn.execute(sql, row)
                        self._conn.execute("RELEASE row")

                    except (self.sqlite3.IntegrityError, self.sqlite3.DataError) as e:
                        self._conn.execute("ROLLBACK TO row")
                        rejects.append((row[0], str(e)))

                self._conn.execute("RELEASE chunk")

        return rejects

    # May be called without any locks held
    def apply(self, upserts, deletes, ratchet_upserts, ratchet_deletes, known_destinations):
        if self.read_only: return 0
        if len(upserts) == 0 and len(deletes) == 0 and len(ratchet_upserts) == 0 and len(ratchet_deletes) == 0: return 0

        with self._flush_lock:
            rows               = []
            removables         = []
            ratchet_rows       = []
            ratchet_removables = []

            for destination_hash in upserts:
                if destination_hash in self._kd_quarantine: continue
                entry = known_destinations.get(destination_hash)
                if entry != None: rows.append(self.__entry_row(destination_hash, entry))

            for destination_hash in deletes:
                if destination_hash not in known_destinations: removables.append((destination_hash,))

            for destination_hash, ratchet_entry in ratchet_upserts.items():
                # Ratchets of purged destinations must be removed as well
                if destination_hash not in known_destinations:         ratchet_removables.append((destination_hash,))
                elif destination_hash not in self._ratchet_quarantine: ratchet_rows.append((destination_hash, *ratchet_entry))

            for destination_hash in ratchet_deletes:
                if destination_hash not in known_destinations: ratchet_removables.append((destination_hash,))

            kd_rejects      = []
            ratchet_rejects = []
            try:
                self._conn.execute("BEGIN")
                kd_rejects      += self.__wrap_exec("INSERT INTO known_destinations (destination_hash, last_heard, packet_hash, public_key, app_data, used, stamp, stamp_value, lr_cost, identity_hash) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(destination_hash) DO UPDATE SET last_heard=excluded.last_heard, packet_hash=excluded.packet_hash, public_key=excluded.public_key, app_data=excluded.app_data, used=excluded.used, stamp=excluded.stamp, stamp_value=excluded.stamp_value, lr_cost=excluded.lr_cost, identity_hash=excluded.identity_hash", rows)
                kd_rejects      += self.__wrap_exec("DELETE FROM known_destinations WHERE destination_hash=?", removables)
                ratchet_rejects += self.__wrap_exec("INSERT INTO ratchets VALUES (?,?,?) ON CONFLICT(destination_hash) DO UPDATE SET ratchet=excluded.ratchet, received=excluded.received", ratchet_rows)
                ratchet_rejects += self.__wrap_exec("DELETE FROM ratchets WHERE destination_hash=?", ratchet_removables)
                self._conn.commit()

            except Exception:
                # If an exception is not handled in the batch query wrapper,
                # we will have to roll back the transaction, and mark all
                # attempted entries as dirty. A failure state like such
                # should not happen, and this is a last resort; at this
                # point, writes may stall until an updated entry for
                # the violating row(s) arrive and heal the invalid
                # dirty entries, so this is raised for logging.
                self._dirty_upsert    |= {row[0] for row in rows}
                self._dirty_delete    |= {row[0] for row in removables}
                self._ratchet_upserts |= {row[0]: row[1:] for row in ratchet_rows}
                self._ratchet_deletes |= {row[0] for row in ratchet_removables}
                self._conn.rollback()
                raise

            # Track failed persists and one-time log per failure. A later
            # update of the destination clears the quarantine state and
            # allows persist to retry with the (hopefully) valid data.
            if len(kd_rejects) > 0 or len(ratchet_rejects) > 0:
                for destination_hash, error in kd_rejects:
                    self._kd_quarantine[destination_hash] = (error, time.time())
                    RNS.log(f"Invalid known destination data for {RNS.prettyhexrep(destination_hash)} at persist. The contained exception was: {error}", RNS.LOG_ERROR)

                for destination_hash, error in ratchet_rejects:
                    self._ratchet_quarantine[destination_hash] = (error, time.time())
                    RNS.log(f"Invalid ratchet data for {RNS.prettyhexrep(destination_hash)} at persist. The contained exception was: {error}", RNS.LOG_ERROR)

            return len(rows)+len(removables)+len(ratchet_rows)+len(ratchet_removables)-len(kd_rejects)-len(ratchet_rejects)

    def load_all(self):
        cursor = self._conn.execute("SELECT destination_hash, last_heard, packet_hash, public_key, app_data, used, stamp, stamp_value, lr_cost FROM known_destinations")
        while True:
            rows = cursor.fetchmany(4096)
            if not rows: break
            for row in rows: yield row[0], [row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8]]

    # Caller must hold Identity.known_destinations_lock.
    def remember_ratchet(self, destination_hash, ratchet, now):
        if self.read_only: return False
        self._ratchet_quarantine.pop(destination_hash, None)

        pending = self._ratchet_upserts.get(destination_hash)
        if pending != None:
            if pending[0] == ratchet:
                self._ratchet_deletes.discard(destination_hash)
                return False

        else:
            row = self._conn.execute("SELECT ratchet FROM ratchets WHERE destination_hash=?", (destination_hash,)).fetchone()
            if row != None and row[0] == ratchet:
                # Discard any pending delete mark queued
                # before this ratchet arrived
                self._ratchet_deletes.discard(destination_hash)
                return False

        self._ratchet_upserts[destination_hash] = (ratchet, now)
        self._ratchet_deletes.discard(destination_hash)
        return True

    def fetch_ratchet(self, destination_hash):
        pending = self._ratchet_upserts.get(destination_hash)
        if pending != None: return pending[0], pending[1]
        if destination_hash in self._ratchet_deletes: return None

        row = self._conn.execute("SELECT ratchet, received FROM ratchets WHERE destination_hash=?", (destination_hash,)).fetchone()
        if row != None: return row[0], row[1]

        return None

    # Caller must hold Identity.known_destinations_lock
    def mark_ratchet_deleted(self, destination_hash):
        if self.read_only: return
        self._ratchet_upserts.pop(destination_hash, None)
        self._ratchet_deletes.add(destination_hash)
        self._ratchet_quarantine.pop(destination_hash, None)

    def expire_ratchets(self, cutoff):
        if self.read_only: return []

        with self._flush_lock:
            # Drop expired entries in pending as well
            expired = set(row[0] for row in self._conn.execute("SELECT destination_hash FROM ratchets WHERE received<?", (cutoff,)))
            for destination_hash, entry in list(self._ratchet_upserts.items()):
                if entry[1] < cutoff:
                    expired.add(destination_hash)
                    self._ratchet_upserts.pop(destination_hash, None)

            expired.difference_update(self._ratchet_deletes)
            if len(expired) > 0:
                self._conn.execute("BEGIN")
                for i in range(0, len(expired), 4096):
                    self._conn.executemany("DELETE FROM ratchets WHERE destination_hash=?", [(h,) for h in list(expired)[i:i+4096]])
                self._conn.commit()

            return list(expired)

    def load_ratchets(self):
        cursor = self._conn.execute("SELECT destination_hash, ratchet, received FROM ratchets")
        while True:
            rows = cursor.fetchmany(4096)
            if not rows: break
            for row in rows: yield row[0], row[1], row[2]

    def import_legacy_ratchets(self, dir_path, expiry_cutoff, known_destinations, ratchet_width=32):
        from .vendor import umsgpack
        imported = 0
        for filename in os.listdir(dir_path):
            file_path = os.path.join(dir_path, filename)
            try:
                if not os.path.isfile(file_path): continue
                with open(file_path, "rb") as rf:
                    ratchet_data = umsgpack.unpackb(rf.read())

                destination_hash = bytes.fromhex(filename)
                ratchet = ratchet_data["ratchet"]; received = ratchet_data["received"]
                if len(ratchet) != ratchet_width: raise ValueError("Invalid ratchet width")
                if received < expiry_cutoff: raise ValueError("Ratchet expired")
                if destination_hash not in known_destinations: raise ValueError("Destination unknown")

                self._ratchet_upserts[destination_hash] = (ratchet, received)
                imported += 1
                os.unlink(file_path)

            except Exception as e:
                RNS.log(f"Could not import ratchet for {filename}: {e}", RNS.LOG_WARNING)
                try: os.unlink(file_path)
                except: pass

        pending = self._ratchet_upserts
        self._ratchet_upserts = {}
        self.apply(set(), set(), pending, set(), known_destinations)

        return imported

    def import_legacy(self, path):
        from .vendor import umsgpack
        with open(path, "rb") as file: legacy = umsgpack.load(file)

        rows = []
        now = time.time()
        for destination_hash, entry in legacy.items():
            if len(entry) < 5: continue
            entry = list(entry)
            while len(entry) < 8: entry.append(None if len(entry) in (5, 7) else 0)
            if entry[0] == None or entry[0] <= 0: entry[0] = now
            rows.append(self.__entry_row(destination_hash, entry))

        self._conn.execute("BEGIN")
        for i in range(0, len(rows), 4096): self._conn.executemany("INSERT OR REPLACE INTO known_destinations (destination_hash, last_heard, packet_hash, public_key, app_data, used, stamp, stamp_value, lr_cost, identity_hash) VALUES (?,?,?,?,?,?,?,?,?,?)", rows[i:i+4096])
        self._conn.commit()

        return len(rows)

class AnnounceCache:

    def __init__(self, db_path):
        import sqlite3
        self.db_path     = db_path
        self._pending    = {}
        self._flush_lock = threading.Lock()
        self._conn       = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)

        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA journal_size_limit=8388608")
        self._conn.execute("PRAGMA auto_vacuum=INCREMENTAL")
        self.__create_schema()

    def __create_schema(self):
        self._conn.execute("""CREATE TABLE IF NOT EXISTS cached_announces (
            packet_hash         BLOB PRIMARY KEY,
            received            REAL NOT NULL,
            raw                 BLOB NOT NULL,
            interface_reference TEXT)""")

        self._conn.execute("PRAGMA user_version = 1")

    def store(self, packet_hash, raw, interface_reference):
        self._pending[packet_hash] = (time.time(), raw, interface_reference)

    def pending_count(self):
        return len(self._pending)

    def fetch(self, packet_hash):
        pending = self._pending.get(packet_hash)
        if pending != None: return pending[1], pending[2]

        row = self._conn.execute("SELECT raw, interface_reference FROM cached_announces WHERE packet_hash=?", (packet_hash,)).fetchone()
        if row != None: return row[0], row[1]

        return None

    def flush(self):
        with self._flush_lock: return self.__apply_pending()

    def __apply_pending(self):
        pending = self._pending
        self._pending = {}
        if len(pending) == 0: return 0

        try:
            self._conn.execute("BEGIN")
            items = list(pending.items())
            for i in range(0, len(items), 4096):
                self._conn.executemany("INSERT INTO cached_announces VALUES (?,?,?,?) ON CONFLICT(packet_hash) DO UPDATE SET received=excluded.received, raw=excluded.raw, interface_reference=excluded.interface_reference",
                                       [(packet_hash, *entry) for packet_hash, entry in items[i:i+4096]])
            self._conn.commit()

        except Exception:
            # Re-mark everything as pending, so the changes
            # are retried on the next flush, then propagate.
            self._pending.update(pending)
            self._conn.rollback()
            raise

        return len(pending)

    def clean(self, active_hashes):
        with self._flush_lock:
            self.__apply_pending()

            try:
                self._conn.execute("BEGIN")
                self._conn.execute("DROP TABLE IF EXISTS temp.active_announces")
                self._conn.execute("CREATE TEMP TABLE active_announces (packet_hash BLOB PRIMARY KEY)")
                active_list = list(active_hashes)
                for i in range(0, len(active_list), 4096):
                    self._conn.executemany("INSERT OR IGNORE INTO active_announces VALUES (?)", [(h,) for h in active_list[i:i+4096]])

                changes_before = self._conn.total_changes
                self._conn.execute("DELETE FROM cached_announces WHERE packet_hash NOT IN (SELECT packet_hash FROM active_announces)")
                removed = self._conn.total_changes - changes_before
                self._conn.commit()

            except Exception:
                self._conn.rollback()
                raise

            if removed > 0: self._conn.execute("PRAGMA incremental_vacuum")

            return removed

    def import_legacy(self, dir_path):
        from .vendor import umsgpack
        imported = 0
        for filename in os.listdir(dir_path):
            file_path = os.path.join(dir_path, filename)
            try:
                if not os.path.isfile(file_path): continue
                with open(file_path, "rb") as file:
                    cached_data = umsgpack.unpackb(file.read())

                packet_hash = bytes.fromhex(filename)
                interface_reference = cached_data[1] if len(cached_data) > 1 else None
                self.store(packet_hash, cached_data[0], interface_reference)
                imported += 1
                os.unlink(file_path)

            except Exception:
                try: os.unlink(file_path)
                except Exception: pass

        self.flush()
        return imported

    def close(self):
        if self._conn != None:
            self._conn.close()
            self._conn = None
