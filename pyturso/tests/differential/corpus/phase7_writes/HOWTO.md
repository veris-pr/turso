# HOWTO — corpus/phase7_writes

Write-path cases: INSERT/DELETE sequences, including fixed-seed randomized
scripts. Every case that writes gets the ride-alongs: sqlite3
`PRAGMA integrity_check` on the pyturso-written file, and dbcompare/dbhash
against a sqlite3-built logical twin.
