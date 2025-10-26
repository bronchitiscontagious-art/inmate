#!/usr/bin/env python3
"""
Simple Inmate Search - Direct Sedgwick County Scraper
User searches → Your backend → Sedgwick County → Results back to user
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

app = Flask(__name__)
CORS(app)

class SedgwickScraper:
    """Simple scraper for Sedgwick County Inmate Search"""
    
    def __init__(self):
        self.base_url = "https://ssc.sedgwickcounty.org/inmatesearch"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.session = requests.Session()
    
    def search_inmates(self, last_name='', first_name='', booking_number=''):
        """
        Search Sedgwick County inmates
        """
        try:
            # Prepare search parameters
            search_url = f"{self.base_url}/SearchResults.aspx"
            
            # First, get the page to get form data
            response = self.session.get(self.base_url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract form data (ViewState, etc.)
            form_data = self._get_form_data(soup)
            
            # Add search parameters
            form_data['txtLastName'] = last_name
            form_data['txtFirstName'] = first_name
            form_data['txtBookingNumber'] = booking_number
            form_data['btnSearch'] = 'Search'
            
            # Submit search
            search_response = self.session.post(
                search_url, 
                data=form_data, 
                headers=self.headers,
                timeout=20
            )
            
            # Parse results
            results_soup = BeautifulSoup(search_response.content, 'html.parser')
            inmates = self._parse_results(results_soup)
            
            return inmates
            
        except Exception as e:
            print(f"Search error: {e}")
            return []
    
    def get_inmate_details(self, inmate_id):
        """Get detailed information for a specific inmate"""
        try:
            detail_url = f"{self.base_url}/InmateDetail.aspx?InmateID={inmate_id}"
            response = self.session.get(detail_url, headers=self.headers, timeout=15)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            details = self._parse_inmate_details(soup)
            return details
            
        except Exception as e:
            print(f"Detail error: {e}")
            return None
    
    def _get_form_data(self, soup):
        """Extract ASP.NET form data"""
        form_data = {}
        
        # Get ViewState
        viewstate = soup.find('input', {'name': '__VIEWSTATE'})
        if viewstate:
            form_data['__VIEWSTATE'] = viewstate.get('value', '')
        
        # Get ViewStateGenerator
        viewstate_gen = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
        if viewstate_gen:
            form_data['__VIEWSTATEGENERATOR'] = viewstate_gen.get('value', '')
        
        # Get EventValidation
        event_val = soup.find('input', {'name': '__EVENTVALIDATION'})
        if event_val:
            form_data['__EVENTVALIDATION'] = event_val.get('value', '')
        
        return form_data
    
    def _parse_results(self, soup):
        """Parse search results"""
        inmates = []
        
        # Look for results table
        table = soup.find('table', {'id': re.compile('GridView', re.I)})
        if not table:
            table = soup.find('table', {'class': re.compile('grid|result', re.I)})
        
        if table:
            rows = table.find_all('tr')[1:]  # Skip header
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    inmate = {
                        'name': self._clean_text(cells[0].text) if len(cells) > 0 else 'N/A',
                        'booking_number': self._clean_text(cells[1].text) if len(cells) > 1 else 'N/A',
                        'booking_date': self._clean_text(cells[2].text) if len(cells) > 2 else 'N/A',
                        'age': self._clean_text(cells[3].text) if len(cells) > 3 else 'N/A',
                        'gender': self._clean_text(cells[4].text) if len(cells) > 4 else 'N/A',
                        'race': self._clean_text(cells[5].text) if len(cells) > 5 else 'N/A',
                        'facility': 'Sedgwick County Jail',
                        'source': 'sedgwick_county'
                    }
                    
                    # Try to extract inmate ID from link
                    link = cells[0].find('a')
                    if link and 'href' in link.attrs:
                        href = link['href']
                        inmate_id_match = re.search(r'InmateID=(\d+)', href)
                        if inmate_id_match:
                            inmate['inmate_id'] = inmate_id_match.group(1)
                    
                    inmates.append(inmate)
        
        return inmates
    
    def _parse_inmate_details(self, soup):
        """Parse detailed inmate information"""
        details = {}
        
        # Extract all label-value pairs
        labels = soup.find_all('span', {'class': re.compile('label', re.I)})
        
        for label in labels:
            label_text = self._clean_text(label.text)
            # Find the value (usually in next sibling)
            value_elem = label.find_next_sibling()
            if value_elem:
                details[label_text] = self._clean_text(value_elem.text)
        
        # Extract charges
        charges_table = soup.find('table', {'id': re.compile('Charges', re.I)})
        if charges_table:
            charges = []
            rows = charges_table.find_all('tr')[1:]
            for row in rows:
                cells = row.find_all('td')
                if cells:
                    charge = ' '.join([self._clean_text(c.text) for c in cells])
                    charges.append(charge)
            details['charges'] = charges
        
        return details
    
    def _clean_text(self, text):
        """Clean and normalize text"""
        if not text:
            return 'N/A'
        text = ' '.join(text.split())
        return text.strip()


# Initialize scraper
scraper = SedgwickScraper()


@app.route('/')
def index():
    """Serve the frontend"""
    return send_from_directory('.', 'simple_search.html')


@app.route('/api/search', methods=['GET'])
def api_search():
    """
    Search inmates
    Parameters: last_name, first_name, booking_number
    """
    last_name = request.args.get('last_name', '')
    first_name = request.args.get('first_name', '')
    booking_number = request.args.get('booking_number', '')
    
    # Must have at least one search parameter
    if not any([last_name, first_name, booking_number]):
        return jsonify({
            'status': 'error',
            'message': 'Please provide at least one search parameter',
            'inmates': []
        }), 400
    
    try:
        inmates = scraper.search_inmates(last_name, first_name, booking_number)
        
        return jsonify({
            'status': 'success',
            'count': len(inmates),
            'inmates': inmates,
            'source': 'Sedgwick County Sheriff - Official Website'
        })
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e),
            'inmates': []
        }), 500


@app.route('/api/details/<inmate_id>', methods=['GET'])
def api_details(inmate_id):
    """Get detailed information for specific inmate"""
    try:
        details = scraper.get_inmate_details(inmate_id)
        
        if details:
            return jsonify({
                'status': 'success',
                'details': details
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Inmate not found'
            }), 404
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'service': 'Simple Inmate Search',
        'source': 'Sedgwick County Official Website',
        'timestamp': datetime.now().isoformat()
    })


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    
    print("🚀 Simple Inmate Search Starting...")
    print(f"📡 Server running on port {port}")
    print("🔍 Direct scraping from Sedgwick County website")
    print("🌐 URL: https://ssc.sedgwickcounty.org/inmatesearch/")
    
    app.run(debug=True, host='0.0.0.0', port=port)
