#!/usr/bin/env python3
"""
HWP API Python Client Example
Simple client library for integrating with HWP extraction API
"""

import requests
import json
import time
import base64
from pathlib import Path
from typing import Optional, Dict, Any, Union
from enum import Enum


class ExtractionFormat(Enum):
    """Supported extraction formats"""
    JSON = "json"
    TEXT = "text"
    MARKDOWN = "markdown"


class HWPAPIClient:
    """
    Client for HWP/HWPX/PDF extraction API
    
    Example usage:
        client = HWPAPIClient("http://localhost:8000")
        
        # Simple extraction
        result = client.extract_file("document.hwp", format=ExtractionFormat.JSON)
        print(result)
        
        # With authentication
        client.authenticate("username", "password")
        result = client.extract_file("document.hwp", authenticated=True)
        
        # Async processing for large files
        task_id = client.extract_async("large_document.pdf")
        result = client.wait_for_result(task_id)
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 300):
        """
        Initialize API client
        
        Args:
            base_url: API base URL
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.token = None
        self.session = requests.Session()
    
    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate and get JWT token
        
        Args:
            username: Username
            password: Password
            
        Returns:
            True if authentication successful
        """
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/auth/token",
                data={
                    "username": username,
                    "password": password
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            
            data = response.json()
            self.token = data["access_token"]
            self.session.headers.update({
                "Authorization": f"Bearer {self.token}"
            })
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Authentication failed: {e}")
            return False
    
    def extract_file(
        self,
        file_path: Union[str, Path],
        format: ExtractionFormat = ExtractionFormat.JSON,
        authenticated: bool = False,
        include_metadata: bool = True,
        include_styles: bool = False
    ) -> Dict[str, Any]:
        """
        Extract text from file synchronously
        
        Args:
            file_path: Path to file
            format: Output format
            authenticated: Use authenticated endpoint
            include_metadata: Include metadata in response
            include_styles: Include style information
            
        Returns:
            Extraction result
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Validate file type
        valid_extensions = {'.hwp', '.hwpx', '.pdf'}
        if file_path.suffix.lower() not in valid_extensions:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")
        
        # Prepare endpoint
        endpoint = f"/api/v1/extract/hwp-to-{format.value}"
        if authenticated:
            endpoint = f"/api/v1/extract/auth/hwp-to-{format.value}"
        
        # Prepare request
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f, 'application/octet-stream')}
            
            data = {}
            if format == ExtractionFormat.JSON:
                if include_metadata:
                    data['include_metadata'] = 'true'
                if include_styles:
                    data['include_styles'] = 'true'
            
            # Send request
            try:
                response = self.session.post(
                    f"{self.base_url}{endpoint}",
                    files=files,
                    data=data,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 413:
                    print(f"File too large ({file_path.stat().st_size} bytes), use async extraction")
                    raise
                elif e.response.status_code == 429:
                    retry_after = e.response.headers.get('Retry-After', 60)
                    print(f"Rate limited, retry after {retry_after} seconds")
                    raise
                else:
                    print(f"Extraction failed: {e}")
                    raise
    
    def extract_async(
        self,
        file_path: Union[str, Path],
        format: ExtractionFormat = ExtractionFormat.JSON,
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Submit file for async extraction
        
        Args:
            file_path: Path to file
            format: Output format
            options: Additional extraction options
            
        Returns:
            Task ID
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Read and encode file
        with open(file_path, 'rb') as f:
            file_content = base64.b64encode(f.read()).decode('utf-8')
        
        # Prepare request
        payload = {
            "file": file_content,
            "filename": file_path.name,
            "extraction_type": format.value,
            "options": options or {}
        }
        
        # Submit job
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/async/submit",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()["task_id"]
            
        except requests.exceptions.RequestException as e:
            print(f"Async submission failed: {e}")
            raise
    
    def check_status(self, task_id: str) -> Dict[str, Any]:
        """
        Check async task status
        
        Args:
            task_id: Task ID
            
        Returns:
            Status information
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/async/status/{task_id}",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Status check failed: {e}")
            raise
    
    def get_result(self, task_id: str) -> Dict[str, Any]:
        """
        Get async task result
        
        Args:
            task_id: Task ID
            
        Returns:
            Extraction result
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/async/result/{task_id}",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Failed to get result: {e}")
            raise
    
    def wait_for_result(
        self,
        task_id: str,
        poll_interval: int = 2,
        max_wait: int = 300
    ) -> Dict[str, Any]:
        """
        Wait for async task to complete and return result
        
        Args:
            task_id: Task ID
            poll_interval: Seconds between status checks
            max_wait: Maximum seconds to wait
            
        Returns:
            Extraction result
        """
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status = self.check_status(task_id)
            
            if status["status"] == "completed":
                return self.get_result(task_id)
            elif status["status"] == "failed":
                raise Exception(f"Task failed: {status.get('error', 'Unknown error')}")
            
            # Show progress if available
            if "progress" in status:
                print(f"Progress: {status['progress']}%")
            
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Task {task_id} did not complete within {max_wait} seconds")
    
    def extract_batch(
        self,
        file_paths: list,
        format: ExtractionFormat = ExtractionFormat.JSON,
        max_concurrent: int = 5
    ) -> Dict[str, Dict[str, Any]]:
        """
        Extract multiple files in batch
        
        Args:
            file_paths: List of file paths
            format: Output format
            max_concurrent: Maximum concurrent requests
            
        Returns:
            Dictionary mapping file paths to results
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        results = {}
        
        def process_file(file_path):
            try:
                # Use async for large files
                if Path(file_path).stat().st_size > 10 * 1024 * 1024:  # > 10MB
                    task_id = self.extract_async(file_path, format)
                    return file_path, self.wait_for_result(task_id)
                else:
                    return file_path, self.extract_file(file_path, format)
            except Exception as e:
                return file_path, {"error": str(e)}
        
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            futures = {executor.submit(process_file, fp): fp for fp in file_paths}
            
            for future in as_completed(futures):
                file_path, result = future.result()
                results[str(file_path)] = result
                print(f"Processed: {file_path}")
        
        return results
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/v1/cache/stats",
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Failed to get cache stats: {e}")
            raise
    
    def clear_cache(self) -> bool:
        """Clear cache"""
        try:
            response = self.session.post(
                f"{self.base_url}/api/v1/cache/clear",
                timeout=self.timeout
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Failed to clear cache: {e}")
            return False
    
    def health_check(self) -> bool:
        """Check API health"""
        try:
            response = self.session.get(
                f"{self.base_url}/health",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            return data.get("status") == "healthy"
        except:
            return False


def main():
    """Example usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description="HWP API Client")
    parser.add_argument("file", help="File to extract")
    parser.add_argument("--url", default="http://localhost:8000", help="API URL")
    parser.add_argument("--format", default="json", choices=["json", "text", "markdown"])
    parser.add_argument("--async", action="store_true", help="Use async processing")
    parser.add_argument("--auth", nargs=2, metavar=("USER", "PASS"), help="Username and password")
    parser.add_argument("--output", help="Output file")
    
    args = parser.parse_args()
    
    # Create client
    client = HWPAPIClient(args.url)
    
    # Check health
    if not client.health_check():
        print(f"API at {args.url} is not healthy")
        return
    
    # Authenticate if requested
    if args.auth:
        username, password = args.auth
        if not client.authenticate(username, password):
            print("Authentication failed")
            return
        print("Authenticated successfully")
    
    # Extract file
    try:
        format = ExtractionFormat(args.format)
        
        if args.async or Path(args.file).stat().st_size > 10 * 1024 * 1024:
            print(f"Using async processing for {args.file}")
            task_id = client.extract_async(args.file, format)
            print(f"Task ID: {task_id}")
            result = client.wait_for_result(task_id)
        else:
            print(f"Extracting {args.file} to {format.value}")
            result = client.extract_file(
                args.file,
                format,
                authenticated=bool(args.auth)
            )
        
        # Output result
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                if format == ExtractionFormat.JSON:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                elif format == ExtractionFormat.TEXT:
                    f.write(result.get('text', ''))
                elif format == ExtractionFormat.MARKDOWN:
                    f.write(result.get('markdown', ''))
            print(f"Result saved to {args.output}")
        else:
            if format == ExtractionFormat.JSON:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            elif format == ExtractionFormat.TEXT:
                print(result.get('text', ''))
            elif format == ExtractionFormat.MARKDOWN:
                print(result.get('markdown', ''))
        
        # Show stats
        if 'processing_time' in result:
            print(f"\nProcessing time: {result['processing_time']:.3f} seconds")
        if 'word_count' in result:
            print(f"Word count: {result['word_count']:,}")
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())