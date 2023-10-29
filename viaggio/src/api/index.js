import axios from 'axios';


const URL = 'https://travel-advisor.p.rapidapi.com/restaurants/list-in-boundary'



export const getPlacesData = async (type, sw, ne) => {
  try {
    const { data: { data } } = await axios.get(URL, {
      params: {
            bl_latitude: sw.lat ,
            tr_latitude: ne.lat ,
            bl_longitude: sw.lng ,
            tr_longitude: ne.lng ,
      },
      headers: {
        'X-RapidAPI-Key': '2730a399d3mshd9e89b142f7aa0ep1e5d10jsn4255c034d234',
        'X-RapidAPI-Host': 'travel-advisor.p.rapidapi.com'
      }
  });
    
    console.log(data)
    return data;
  } catch (error) {
    console.log(error)
  }
};

/*export const getWeatherData = async ( lat, lng ) => {
  const axios = require('axios');

const options = {
  method: 'GET',
  url: `https://forecast9.p.rapidapi.com/rapidapi/forecast/${lat}/${lng}/summary/`,
  headers: {
    'X-RapidAPI-Key': 'd922508a0fmsh8d03f9ece8d4fbdp1b6878jsn4f353ffcbe0b',
    'X-RapidAPI-Host': 'forecast9.p.rapidapi.com'
  }
};

try {
	const response = await axios.request(getData(id)); const data = res.data
	console.log(response.data);
} catch (error) {
	console.error(error);
}}*/