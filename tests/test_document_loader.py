import pandas as pd

from backend.rag.document_loader import _dataframe_to_lines


def test_ticket_narrative_column_extracted_and_others_dropped():
    """A helpdesk export where one column packs the whole open/assigned/
    response/closed history into one cell: that column's opened/closed text
    plus the VIN (unique per-vehicle handle for exact-match retrieval)
    survive; every other metadata column (Ticket Number, dates) is dropped
    as noise."""
    df = pd.DataFrame(
        {
            "Ticket Number": ["SR#1", "SR#2"],
            "VIN": ["MEC0024T2SP074314", "-"],
            "Open Date": ["2025-12-31", "2025-12-31"],
            "Remarks": [
                "Open (31.12.2025) : 15:37:49 : Need part for seat belt."
                "Assigned (05.01.2026) : 00:00:16 : -"
                "Response (05.01.2026) : 09:34:43 : GENTLE REMINDER"
                "Closed (05.01.2026) : Part number is MK324092. Thank you.",
                "Open (31.12.2025) : 04:03:48 : Need propeller shaft part number."
                "Closed (02.01.2026) : Part number is MX910051. Thank you.",
            ],
        }
    )
    lines = _dataframe_to_lines(df)
    assert len(lines) == 2
    assert lines[0] == (
        "VIN: MEC0024T2SP074314; "
        "Opened: Need part for seat belt.; "
        "Closed: Part number is MK324092. Thank you."
    )
    # Placeholder '-' VIN must be skipped, not rendered.
    assert lines[1] == (
        "Opened: Need propeller shaft part number.; "
        "Closed: Part number is MX910051. Thank you."
    )
    # Metadata that isn't the narrative or VIN must not leak in.
    for line in lines:
        assert "SR#" not in line
        assert "2025-12-31" not in line


def test_plain_tabular_data_keeps_all_columns():
    """Ordinary spreadsheets (no open/closed narrative) must render every
    column exactly as before — this path must not regress for non-ticket
    documents like product lists."""
    df = pd.DataFrame(
        {
            "SKU": ["0001", "0002"],
            "Name": ["Widget", "Gadget"],
            "Price": ["10", "20"],
        }
    )
    lines = _dataframe_to_lines(df)
    assert lines == [
        "SKU: 0001; Name: Widget; Price: 10",
        "SKU: 0002; Name: Gadget; Price: 20",
    ]
