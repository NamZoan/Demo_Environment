from app.repository import normalize_ftp_catalog_row


def test_normalize_ftp_catalog_row_decodes_json_station_list():
    result = normalize_ftp_catalog_row({"id": 3, "stations": "[]", "station_ids": []})

    assert result["stations"] == []
