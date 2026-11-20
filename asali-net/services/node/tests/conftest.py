from pathlib import Path

import pytest
from asali_node.settings import Settings


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        org_id="shop-mumbai",
        org_type="shop",
        org_name="Apna Chemist",
        org_city="Mumbai",
        org_state="MH",
        engine="sqlite",
        sqlite_path=tmp_path / "shop.sqlite",
        db_rw_url="postgresql://app_rw:secret-pass@db:5432/shop",
        db_ro_url="postgresql://share_ro:secret-pass@db:5432/shop",
        meili_url="http://vault:7700",
        meili_master_key="meili-master-secret",
        directory_url="https://10.0.0.1:8400",
        join_token="join-secret",
        public_base_url="https://10.0.0.4:8202",
        host_name="PC-D",
        asali_mode="simulation",
        data_dir=tmp_path,
        shop_settings_json='{"area": "Andheri", "receipt_language": "mr", "drug_licence_no": "MH-1", "salt": "shop-private-salt"}',
    )
