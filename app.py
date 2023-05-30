from flask import Flask, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
import random
import csv
from datetime import timedelta, datetime,time
from pytz import timezone
import pandas as pd

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://root:@localhost/loopkitchen'
db = SQLAlchemy()
# Initialize the SQLAlchemy app
db.init_app(app)

class StoreStatus(db.Model):
    """
    Model class for the store_status table.
    """
    __tablename__ = 'store_status'
    
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, nullable=False)
    timestamp_utc = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(10), nullable=False)
    
class StoreBusinessHours(db.Model):
    """
    Model class for the store_business_hours table.
    """
    __tablename__ = 'store_business_hours'
    
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)
    start_time_local = db.Column(db.Time)
    end_time_local = db.Column(db.Time)
    
class StoreTimezone(db.Model):
    """
    Model class for the store_timezone table.
    """
    __tablename__ = 'store_timezone'
    
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, nullable=False)
    timezone_str = db.Column(db.String(50))

class Report(db.Model):
    """
    Model class for the reports table.
    """
    __tablename__ = 'reports'

    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    file_path = db.Column(db.String(100), nullable=False)

@app.route('/trigger_report', methods=['GET'])
def trigger_report():
    """
    Trigger the generation of a new report.
    This route will be called to initiate the report generation process.

    Returns:
        JSON response containing the report_id.
    """
    report_id = generate_report()
    return jsonify({'report_id': report_id})

@app.route('/get_report/<report_id>', methods=['GET'])
def get_report(report_id):
    """
    Retrieve the generated report.
    This route will be called to fetch the generated report by providing the report_id.

    Args:
        report_id (str): The unique identifier of the report.

    Returns:
        If the report is complete, the CSV file is returned as the API response.
        If the report is not complete, the response contains the status of the report.
    """
    status = check_report_status(report_id)
    if status == 'Complete':
        report_file_path = generate_report_file_path(report_id)
        return send_file(report_file_path, mimetype='text/csv', as_attachment=True)
    else:
        return jsonify({'status': status})

def generate_report():
    """
    Generate a new report based on the store status and business hours data.

    Returns:
        str: The unique identifier of the generated report.
    """
    # Get the current timestamp
    current_timestamp = datetime.utcnow()

    # Fetch store timezones from the database
    store_timezones = StoreTimezone.query.all()
    store_timezones_dict = {timezone.store_id: timezone.timezone_str for timezone in store_timezones}

    # Fetch store business hours from the database
    store_business_hours = StoreBusinessHours.query.all()
    store_business_hours_dict = {(hour.store_id, hour.day_of_week): (hour.start_time_local, hour.end_time_local) for hour in store_business_hours}

    # Define the report structure
    report = {
        'store_id': [],
        'uptime_last_hour': [],
        'uptime_last_day': [],
        'uptime_last_week': [],
        'downtime_last_hour': [],
        'downtime_last_day': [],
        'downtime_last_week': []
    }

    # Fetch store status from the database
    store_status_records = StoreStatus.query.all()

    # Fetch store status from the database
    for record in store_status_records:
        store_id = record.store_id
        timestamp_utc = record.timestamp_utc
        status = record.status

        # Convert UTC timestamp to store's local timezone
        store_timezone = store_timezones_dict.get(store_id, 'America/Chicago')
        tz = timezone(store_timezone)
        timestamp_local = timestamp_utc.astimezone(tz)

        # Calculate uptime and downtime based on business hours
        start_time_local, end_time_local = store_business_hours_dict.get((store_id, timestamp_local.weekday()), (None, None))
        if start_time_local and end_time_local:
            start_time_local = datetime.combine(timestamp_local.date(), start_time_local)
            end_time_local = datetime.combine(timestamp_local.date(), end_time_local)

            # Convert start_time_local and end_time_local to the same timezone as timestamp_local
            start_time_local = start_time_local.replace(tzinfo=tz)
            end_time_local = end_time_local.replace(tzinfo=tz)

            if start_time_local <= timestamp_local <= end_time_local:
                # The store is within business hours
                if status == 'active':
                    uptime_last_hour = (end_time_local - timestamp_local).seconds // 60
                    uptime_last_day = (end_time_local - start_time_local).seconds // 3600
                    uptime_last_week = uptime_last_day * 7
                    downtime_last_hour = 0
                    downtime_last_day = 0
                    downtime_last_week = 0
                else:
                    uptime_last_hour = 0
                    uptime_last_day = 0
                    uptime_last_week = 0
                    downtime_last_hour = (end_time_local - timestamp_local).seconds // 60
                    downtime_last_day = (end_time_local - start_time_local).seconds // 3600
                    downtime_last_week = downtime_last_day * 7
            else:
                # The store is outside business hours
                uptime_last_hour = 0
                uptime_last_day = 0
                uptime_last_week = 0
                downtime_last_hour = 0
                downtime_last_day = 0
                downtime_last_week = 0
        else:
            # Assume the store is open 24*7
            if status == 'active':
                uptime_last_hour = 60
                uptime_last_day = 24
                uptime_last_week = uptime_last_day * 7
                downtime_last_hour = 0
                downtime_last_day = 0
                downtime_last_week = 0
            else:
                uptime_last_hour = 0
                uptime_last_day = 0
                uptime_last_week = 0
                downtime_last_hour = 60
                downtime_last_day = 24
                downtime_last_week = downtime_last_day * 7


        # Append the data to the report
        report['store_id'].append(store_id)
        report['uptime_last_hour'].append(uptime_last_hour)
        report['uptime_last_day'].append(uptime_last_day)
        report['uptime_last_week'].append(uptime_last_week)
        report['downtime_last_hour'].append(downtime_last_hour)
        report['downtime_last_day'].append(downtime_last_day)
        report['downtime_last_week'].append(downtime_last_week)


    # Generate a unique report_id
    report_id = generate_random_string()

    # Save the report to a CSV file
    report_file_path = f'reports/report_{report_id}.csv'
    with open(report_file_path, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['store_id', 'uptime_last_hour', 'uptime_last_day', 'uptime_last_week',
                         'downtime_last_hour', 'downtime_last_day', 'downtime_last_week'])
        for i in range(len(report['store_id'])):
            writer.writerow([
                report['store_id'][i],
                report['uptime_last_hour'][i],
                report['uptime_last_day'][i],
                report['uptime_last_week'][i],
                report['downtime_last_hour'][i],
                report['downtime_last_day'][i],
                report['downtime_last_week'][i]
            ])

    # Update the report status in the database
    report_status = Report(report_id=report_id, status='Complete', file_path=report_file_path)
    db.session.add(report_status)
    db.session.commit()

    return report_id



def check_report_status(report_id):
    # Query the report status from the database based on the report_id
    report_status = db.session.query(Report).filter_by(report_id=report_id).first()

    # If the report exists, return its status
    if report_status:
        return report_status.status
    else:
        return 'Report not found'  # Or any other appropriate message


def generate_report_file_path(report_id):
    # Generate the file path of the report based on the report_id
    # Return the file path
    return f'reports/report_{report_id}.csv'

def generate_random_string(length=10):
    # Generate a random string of given length
    # Return the random string
    characters = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'
    return ''.join(random.choice(characters) for _ in range(length))

if __name__ == '__main__':
    app.run()
