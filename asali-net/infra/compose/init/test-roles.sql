-- Same two roles the tests expect when the engines come from test-engines.yml (see local_engines.py).
CREATE ROLE app_rw LOGIN PASSWORD 'app_rw_pw' CREATEDB;
CREATE ROLE share_ro LOGIN PASSWORD 'share_ro_pw';
