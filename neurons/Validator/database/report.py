# The MIT License (MIT)
# Copyright © 2023 Rapiiidooo
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

from typing import Optional
import bittensor as bt
from datetime import datetime

from compute.utils.db import ComputeDb


#  Update the hotkey_reliability_report db
def update_hotkey_reliability_report_db(reports: list):
    db = ComputeDb()
    cursor = db.get_cursor()
    try:

        # Prepare data for bulk insert
        report_details_to_insert = [
            (
                datetime.strptime(report.timestamp, '%Y-%m-%dT%H:%M:%S.%fZ'),
                report.hotkey,
                report.rentals,
                report.failed,
                report.short_rental,
                report.rentals_14d,
                report.failed_14d,
                report.short_rental_14d,
                report.aborted,
                report.rental_best,
                report.blacklisted
            )
            for report in reports
        ]
        # Perform bulk insert using executemany
        cursor.executemany(
            "INSERT INTO hotkey_reliability_report"
            "(timestamp, hotkey, rentals, failed, short_rental, rentals_14d, failed_14d, aborted, rental_best, short_rental_14d, blacklisted)"
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            report_details_to_insert,
        )
        db.conn.commit()
    except Exception as e:
        db.conn.rollback()
        bt.logging.error(f"Error while updating hotkey_reliability_report: {e}")
    finally:
        cursor.close()
        db.close()


def get_hotkey_reliability_reports_db(db: ComputeDb, hotkey: Optional[str] = None) -> list[dict]:
    """
    Retrieves the hotkey reliability reports for all hotkeys or given hotkey from the database.

    :param db: An instance of ComputeDb to interact with the database.
    :param hotkey: Optional filter to query database for specific hotkey.
    :return: A list with data from each row of the table.
    """
    hotkey_reliability_reports = []
    cursor = db.get_cursor()
    try:
        query = """
            SELECT
                timestamp,
                hotkey,
                rentals,
                failed,
                short_rental,
                rentals_14d,
                failed_14d,
                short_rental_14d,
                aborted,
                rental_best,
                blacklisted
            FROM hotkey_reliability_report
            {hotkey}
            ORDER BY timestamp
        """.format(
            hotkey = ' WHERE hotkey = ?' if hotkey else ''
        )
        if hotkey:
            cursor.execute(query, (hotkey,))
        else:
            # Fetch all records from hotkey_reliability_report table
            cursor.execute(query)
        rows = cursor.fetchall()

        # Create a dictionary from the fetched rows
        hotkey_reliability_reports = [
            {
                # format to the right datetime format as input: %Y-%m-%dT%H:%M:%S.%fZ
                'timestamp': datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S.%f').strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
                'hotkey': hotkey,
                'rentals': rentals,
                'failed': failed,
                'short_rental': short_rental,
                'rentals_14d': rentals_14d,
                'failed_14d': failed_14d,
                'short_rental_14d': short_rental_14d,
                'aborted': aborted,
                'rental_best': rental_best,
                'blacklisted': bool(blacklisted),
            }
            for timestamp,
                hotkey,
                rentals,
                failed,
                short_rental,
                rentals_14d,
                failed_14d,
                short_rental_14d,
                aborted,
                rental_best,
                blacklisted in rows
        ]
    except Exception as e:
        bt.logging.error(f"Error while retrieving hotkey reliability reports: {e}")
    finally:
        cursor.close()

    return hotkey_reliability_reports
