import React from 'react';
import ReactDOM from 'react-dom';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';

import Contact from '../src/components/contact';
import Index from '../src/components/index';
import Blog from '../src/components/blog';
import Gallery from '../src/components/gallery';
import About from '../src/components/about';

import App from './App';
import Login from './components/auth/login';
import Book from './components/book/book';
import FHome from './components/Flights/FHome';
import FlightList from './components/Flights/FlightList';
import HHome from './components/Hotels/HHome';


const root = document.getElementById('root');

// ReactDOM.render(
//   <Router>
//     <Route path="/" exact component={Index} />
//     <Route path="/about" component={About} />
//     <Route path="/blog" component={Blog} />
//     <Route path="/contact" component={Contact} />
//     <Route path="/gallery" component={Gallery} />
//     <Route path="/App" component={App} />
//   </Router>,
//   root
// );

// import { Route, Routes } from 'react-router-dom';

ReactDOM.render(
  <Router>
    <Routes>
      <Route path="/" element={<Index />} />
      <Route path="/about" element={<About />} />
      <Route path="/blog" element={<Blog />} />
      <Route path="/contact" element={<Contact />} />
      <Route path="/gallery" element={<Gallery />} />
      <Route path="/fhome" element={<FHome />} />
      <Route path="/flightlist" element={<FlightList />} />
      <Route path="/book" element={<Book />} />
      <Route path="/login" element={<Login />} />
      <Route path="/hhome" element={<HHome />} />
      <Route path="/App" element={<App />} />
    </Routes>
  </Router>,
  root
);
