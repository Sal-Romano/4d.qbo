import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/Login.css';

const Login: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [otp, setOtp] = useState('');
  const [showOtp, setShowOtp] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [isDarkTheme, setIsDarkTheme] = useState(true);
  const navigate = useNavigate();

  // Initialize theme from local storage or default to dark
  useEffect(() => {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    setIsDarkTheme(savedTheme === 'dark');
  }, []);

  const toggleTheme = () => {
    const newTheme = isDarkTheme ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    setIsDarkTheme(!isDarkTheme);
  };

  const togglePasswordVisibility = () => {
    const passwordInput = document.getElementById('password') as HTMLInputElement;
    if (passwordInput) {
      passwordInput.type = passwordInput.type === 'password' ? 'text' : 'password';
      const icon = document.querySelector('.toggle-password') as HTMLElement;
      if (icon) {
        icon.classList.toggle('fa-eye');
        icon.classList.toggle('fa-eye-slash');
      }
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage('');
    
    // Simple validation
    if (!username || !password) {
      setErrorMessage('Please enter both email and password');
      return;
    }

    // Placeholder for authentication logic
    if (!showOtp) {
      // First step: validate credentials
      // For now, just show OTP field (this would normally come from server)
      setShowOtp(true);
      return;
    }

    // Second step: validate OTP
    if (otp === '123456') { // Dummy OTP check
      setSuccessMessage('Login successful');
      // Redirect to dashboard after successful login
      setTimeout(() => navigate('/dashboard'), 1000);
    } else {
      setErrorMessage('Invalid two-factor code');
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>VOXCON.AI</h1>
          <button  
            id="theme-toggle" 
            className="theme-toggle" 
            title="Toggle theme"
            onClick={toggleTheme}
          >
            <i className="fas fa-moon dark-icon"></i>
            <i className="fas fa-sun light-icon"></i>
          </button>
        </div>
        
        {errorMessage && (
          <div className="error-message visible">
            {errorMessage}
          </div>
        )}
        
        {successMessage && (
          <div className="success-message visible">
            {successMessage}
          </div>
        )}
        
        <form id="login-form" onSubmit={handleSubmit}>
          <div className="input-group">
            <label htmlFor="username">
              <i className="fas fa-user"></i>
              Email
            </label>
            <input 
              type="email" 
              id="username" 
              name="username" 
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required 
            />
          </div>
          
          <div className="input-group">
            <label htmlFor="password">
              <i className="fas fa-lock"></i>
              Password
            </label>
            <div className="password-input">
              <input 
                type="password" 
                id="password" 
                name="password" 
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required 
              />
              <i 
                className="fas fa-eye toggle-password"
                onClick={togglePasswordVisibility}
              ></i>
            </div>
          </div>
          
          {showOtp && (
            <div className="input-group otp-group">
              <label htmlFor="otp">
                <i className="fas fa-key"></i>
                Two-Factor Code
              </label>
              <input 
                type="text" 
                id="otp" 
                name="otp" 
                pattern="[0-9]*" 
                inputMode="numeric"
                value={otp}
                onChange={(e) => setOtp(e.target.value)}
              />
            </div>
          )}
          
          <div id="error-message" className="error-message"></div>
          
          <button type="submit" className="login-btn">
            <i className="fas fa-sign-in-alt"></i>
            Login
          </button>
        </form>
      </div>
    </div>
  );
};

export default Login; 