#!/usr/bin/env python3
"""
Email Tracking Server
Tracks email opens via pixel tracking
"""

from flask import Flask, Response, request, redirect
import sqlite3
from datetime import datetime
import io
import uuid
import re
from PIL import Image

app = Flask(__name__)

# 1x1 transparent pixel
TRACKING_PIXEL = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'

def init_database():
    """Initialize the tracking database"""
    conn = sqlite3.connect('email_tracking.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_tracking (
            tracking_id TEXT PRIMARY KEY,
            recipient_email TEXT,
            subject TEXT,
            sent_at TIMESTAMP,
            opened_at TIMESTAMP,
            open_count INTEGER DEFAULT 0,
            user_agent TEXT,
            ip_address TEXT
        )
    ''')
    conn.commit()
    conn.close()
    
    # Also initialize link tracking
    conn = sqlite3.connect('link_tracking.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS link_tracking (
            link_id TEXT PRIMARY KEY,
            original_url TEXT,
            email_id TEXT,
            recipient_email TEXT,
            created_at TIMESTAMP,
            click_count INTEGER DEFAULT 0,
            last_clicked TIMESTAMP,
            user_agent TEXT,
            ip_address TEXT
        )
    ''')
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

@app.route('/')
def home():
    """Home page for tracking server"""
    return '''
    <html>
    <head><title>Email Tracking Server</title></head>
    <body>
        <h1>📧 Email Tracking Server</h1>
        <p>✅ Server is running successfully!</p>
        <h2>Available Pages:</h2>
        <ul>
            <li><a href="/stats">📊 View Email Open Statistics</a></li>
            <li><a href="/link-stats">🔗 View Link Click Statistics</a></li>
            <li><a href="/debug">🔧 Debug Database</a></li>
        </ul>
        <p><strong>Server Status:</strong> Active and ready to track emails</p>
    </body>
    </html>
    '''

@app.route('/track/<tracking_id>')
def track_email(tracking_id):
    """Track email open and return transparent pixel"""
    try:
        # Get tracking info
        user_agent = request.headers.get('User-Agent', 'Unknown')
        ip_address = request.remote_addr
        
        print(f"📧 Email opened! Tracking ID: {tracking_id}")
        print(f"   User Agent: {user_agent}")
        print(f"   IP Address: {ip_address}")
        
        # Update database
        conn = sqlite3.connect('email_tracking.db')
        cursor = conn.cursor()
        
        # Check if tracking ID exists
        cursor.execute('SELECT open_count FROM email_tracking WHERE tracking_id = ?', (tracking_id,))
        result = cursor.fetchone()
        
        if result:
            open_count = result[0] or 0
            
            # Update tracking record
            cursor.execute('''
                UPDATE email_tracking 
                SET opened_at = ?, 
                    open_count = ?, 
                    user_agent = ?, 
                    ip_address = ?
                WHERE tracking_id = ?
            ''', (datetime.now(), open_count + 1, user_agent, ip_address, tracking_id))
            
            conn.commit()
            print(f"   ✓ Database updated - Open count: {open_count + 1}")
        else:
            print(f"   ✗ Tracking ID not found in database: {tracking_id}")
        
        conn.close()
        
    except Exception as e:
        print(f"Tracking error: {e}")
    
    # Return transparent pixel
    return Response(TRACKING_PIXEL, mimetype='image/gif')

@app.route('/stats')
def view_stats():
    """View email tracking statistics"""
    conn = sqlite3.connect('email_tracking.db')
    cursor = conn.cursor()
    
    # Get all tracking data
    cursor.execute('''
        SELECT 
            recipient_email,
            subject,
            sent_at,
            opened_at,
            open_count,
            user_agent
        FROM email_tracking
        ORDER BY sent_at DESC
        LIMIT 100
    ''')
    
    results = cursor.fetchall()
    conn.close()
    
    # Build HTML response
    html = '<html><head><title>Email Tracking Stats</title>'
    html += '<style>table {border-collapse: collapse; width: 100%;} th, td {border: 1px solid #ddd; padding: 8px; text-align: left;} th {background-color: #f2f2f2;}</style>'
    html += '</head><body><h1>Email Tracking Statistics</h1>'
    
    # Add debug info
    html += f'<p>Database path: email_tracking.db</p>'
    html += f'<p>Total records: {len(results)}</p>'
    
    html += '<table><tr><th>Recipient</th><th>Subject</th><th>Sent</th><th>Opened</th><th>Opens</th><th>User Agent</th></tr>'
    
    if not results:
        html += '<tr><td colspan="6">No emails tracked yet. Make sure to send emails with tracking enabled.</td></tr>'
    else:
        for row in results:
            opened = row[3] if row[3] else 'Not opened'
            opens = row[4] if row[4] else 0
            html += f'<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td><td>{opened}</td><td>{opens}</td><td>{row[5] or "N/A"}</td></tr>'
    
    html += '</table></body></html>'
    
    return html

@app.route('/api/stats/<recipient_email>')
def get_recipient_stats(recipient_email):
    """Get stats for specific recipient (API endpoint)"""
    conn = sqlite3.connect('email_tracking.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            tracking_id,
            subject,
            sent_at,
            opened_at,
            open_count
        FROM email_tracking
        WHERE recipient_email = ?
        ORDER BY sent_at DESC
    ''', (recipient_email,))
    
    results = cursor.fetchall()
    conn.close()
    
    stats = []
    for row in results:
        stats.append({
            'tracking_id': row[0],
            'subject': row[1],
            'sent_at': row[2],
            'opened_at': row[3],
            'open_count': row[4] or 0
        })
    
    return {'recipient': recipient_email, 'emails': stats}

@app.route('/debug')
def debug_database():
    """Debug database contents"""
    try:
        conn = sqlite3.connect('email_tracking.db')
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_tracking'")
        table_exists = cursor.fetchone()
        
        # Count records
        cursor.execute("SELECT COUNT(*) FROM email_tracking")
        count = cursor.fetchone()[0] if table_exists else 0
        
        # Get all records
        cursor.execute("SELECT * FROM email_tracking ORDER BY sent_at DESC")
        records = cursor.fetchall()
        
        conn.close()
        
        html = '<html><body><h1>Database Debug</h1>'
        html += f'<p>Table exists: {bool(table_exists)}</p>'
        html += f'<p>Record count: {count}</p>'
        html += '<h2>All Records:</h2>'
        html += '<pre>'
        for record in records:
            html += str(record) + '\n'
        html += '</pre>'
        html += '</body></html>'
        
        return html
        
    except Exception as e:
        return f'<html><body><h1>Debug Error</h1><p>{str(e)}</p></body></html>'

@app.route('/test-tracking/<tracking_id>')
def test_tracking(tracking_id):
    """Test tracking by manually triggering it"""
    try:
        # Simulate email open
        conn = sqlite3.connect('email_tracking.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT open_count FROM email_tracking WHERE tracking_id = ?', (tracking_id,))
        result = cursor.fetchone()
        
        if result:
            open_count = result[0] or 0
            cursor.execute('''
                UPDATE email_tracking 
                SET opened_at = ?, 
                    open_count = ?, 
                    user_agent = ?, 
                    ip_address = ?
                WHERE tracking_id = ?
            ''', (datetime.now(), open_count + 1, 'Test Browser', '127.0.0.1', tracking_id))
            conn.commit()
            
            return f'<html><body><h1>Test Tracking</h1><p>Successfully updated tracking for ID: {tracking_id}</p><p>New open count: {open_count + 1}</p></body></html>'
        else:
            return f'<html><body><h1>Test Tracking</h1><p>Tracking ID not found: {tracking_id}</p></body></html>'
            
        conn.close()
        
    except Exception as e:
        return f'<html><body><h1>Test Error</h1><p>{str(e)}</p></body></html>'

@app.route('/click/<link_id>')
def track_link_click(link_id):
    """Track link click and redirect to original URL"""
    try:
        user_agent = request.headers.get('User-Agent', 'Unknown')
        ip_address = request.remote_addr
        
        print(f"🔗 Link clicked! Link ID: {link_id}")
        print(f"   User Agent: {user_agent}")
        print(f"   IP Address: {ip_address}")
        
        conn = sqlite3.connect('link_tracking.db')
        cursor = conn.cursor()
        
        # Get original URL and update click count
        cursor.execute('SELECT original_url, click_count FROM link_tracking WHERE link_id = ?', (link_id,))
        result = cursor.fetchone()
        
        if result:
            original_url, click_count = result
            
            # Update click tracking
            cursor.execute('''
                UPDATE link_tracking 
                SET click_count = ?, 
                    last_clicked = ?, 
                    user_agent = ?, 
                    ip_address = ?
                WHERE link_id = ?
            ''', (click_count + 1, datetime.now(), user_agent, ip_address, link_id))
            
            conn.commit()
            conn.close()
            
            print(f"   ✓ Redirecting to: {original_url}")
            print(f"   ✓ Click count: {click_count + 1}")
            
            # Redirect to original URL
            return redirect(original_url)
        else:
            conn.close()
            return "Link not found", 404
            
    except Exception as e:
        print(f"Link tracking error: {e}")
        return "Error processing link", 500

@app.route('/link-stats')
def view_link_stats():
    """View link tracking statistics"""
    conn = sqlite3.connect('link_tracking.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            recipient_email,
            original_url,
            click_count,
            last_clicked,
            created_at
        FROM link_tracking
        ORDER BY last_clicked DESC, created_at DESC
        LIMIT 100
    ''')
    
    results = cursor.fetchall()
    conn.close()
    
    # Build HTML response
    html = '<html><head><title>Link Tracking Stats</title>'
    html += '<style>table {border-collapse: collapse; width: 100%;} th, td {border: 1px solid #ddd; padding: 8px; text-align: left;} th {background-color: #f2f2f2;}</style>'
    html += '</head><body><h1>🔗 Link Tracking Statistics</h1>'
    
    html += f'<p>Total tracked links: {len(results)}</p>'
    html += '<table><tr><th>Recipient</th><th>Original URL</th><th>Clicks</th><th>Last Clicked</th><th>Created</th></tr>'
    
    if not results:
        html += '<tr><td colspan="5">No link clicks tracked yet.</td></tr>'
    else:
        for row in results:
            last_clicked = row[3] if row[3] else 'Never'
            # Truncate long URLs
            url_display = row[1][:50] + '...' if len(row[1]) > 50 else row[1]
            html += f'<tr><td>{row[0]}</td><td title="{row[1]}">{url_display}</td><td>{row[2]}</td><td>{last_clicked}</td><td>{row[4]}</td></tr>'
    
    html += '</table></body></html>'
    
    return html

if __name__ == '__main__':
    # Initialize database first
    init_database()
    
    # Run server
    print("Starting email tracking server on http://localhost:5000")
    print("View stats at: http://localhost:5000/stats")
    app.run(host='0.0.0.0', port=5000, debug=True)
