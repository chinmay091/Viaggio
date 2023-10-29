import React from 'react';
import "./FCard.css";
import { Link } from 'react-router-dom';
import FlightIcon from '@mui/icons-material/Flight';
import PropTypes from 'prop-types';

function FCard({
  filteredflights,
}) {
  return (
    <div className='card__container'>
      {filteredflights && filteredflights.map((flight, index) => (
        <div className='card' key={index}>
          <div className='card__info'>
            <div className='row1'>
              <div>airline: <span>{flight?.airlineName || ""}</span></div>
            </div>
            <div className='row1'>
              <p>from: {flight?.from || ""}<span></span></p>
              <p>via: <span>{flight?.via[0] || ""}</span></p>
              <p>to: <span>{flight?.to || ""}</span></p>
            </div>
            <div className='row2'>
              <p>departure: <span>{flight?.departure?.departureTime || ""} | {flight?.departure?.departureDate || ""}</span></p>
              <p>return: <span>{flight?.return?.returnTime || ""} | {flight?.return?.returnDate || ""}</span></p>
            </div>
            <div className='row3'>
              <p>Duration: <span>{flight?.duration || ""}</span></p>
              <p>Price: <span>{flight?.price || ""}</span></p>
            </div>
          </div>
          <div className='card__btn'>
            <Link to='/book'>Book</Link>
          </div>
        </div>
      ))}
    </div>
  );
}

FCard.propTypes = {
  filteredflights: PropTypes.arrayOf(
    PropTypes.shape({
      airlineName: PropTypes.string,
      from: PropTypes.string,
      via: PropTypes.arrayOf(PropTypes.string),
      to: PropTypes.string,
      departure: PropTypes.shape({
        departureTime: PropTypes.string,
        departureDate: PropTypes.string,
      }),
      return: PropTypes.shape({
        returnTime: PropTypes.string,
        returnDate: PropTypes.string,
      }),
      duration: PropTypes.string,
      price: PropTypes.string,
    })
  ),
};

export default FCard;
