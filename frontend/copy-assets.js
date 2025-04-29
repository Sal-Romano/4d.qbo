// Simple script to copy assets during build
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Source and destination paths
const srcDir = path.join(__dirname, 'src', 'assets');
const destDir = path.join(__dirname, 'dist', 'assets');

// Create destination directory if it doesn't exist
if (!fs.existsSync(destDir)) {
  fs.mkdirSync(destDir, { recursive: true });
}

// Function to copy directory recursively
function copyDirectory(src, dest) {
  const entries = fs.readdirSync(src, { withFileTypes: true });
  
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    
    // Create directory if it doesn't exist
    if (entry.isDirectory()) {
      if (!fs.existsSync(destPath)) {
        fs.mkdirSync(destPath, { recursive: true });
      }
      copyDirectory(srcPath, destPath);
    } else {
      // Copy file
      fs.copyFileSync(srcPath, destPath);
      console.log(`Copied: ${srcPath} -> ${destPath}`);
    }
  }
}

try {
  // Copy assets directory
  copyDirectory(srcDir, destDir);
  console.log('Successfully copied assets!');
} catch (error) {
  console.error('Error copying assets:', error);
} 