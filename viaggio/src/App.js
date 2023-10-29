import React, { useState, useEffect } from 'react';
import { CssBaseline, Grid } from '@material-ui/core';

import { getPlacesData } from './api';
import Header from './components/header/header';
import List from './components/list/list';
import Map from './components/map/map';
// import SentimentAnalysisWithStars from './components/SentimentAnalysis';
// import SentimentAnalysis from './components/SentimentAnalysis';



const App = () => {
    const [places, setPlaces] = useState([]);
    // console.log(places)
    // const [weatherData, setWeatherData] = useState([]);
    const [filteredPlaces, setfilteredPlaces] = useState([]);
    const [childClicked, setchildClicked] = useState(null);

    const [coordinates, setCoordinates] = useState({});
    const [bounds, setBounds] = useState({});

    const [isLoading, setisLoading] = useState(false);
    const [type, setType] = useState('');
    const [rating, setRating] = useState('');

    // const fetchlatdata = async () => {
    //     await navigator.geolocation.getCurrentPosition(({ coords: { latitude, longitude } }) => {
    //         setCoordinates({ lat: latitude, lng: longitude });
        
    //     })

    useEffect(() => {
            navigator.geolocation.getCurrentPosition(({ coords: { latitude, longitude } }) => {
                setCoordinates({ lat: latitude, lng: longitude });
                // console.log(coordinates);
            })
        }, []);

        useEffect(() => {
            const filteredPlaces = places.filter((place) => place.rating > rating);
            setfilteredPlaces(filteredPlaces);
        }, [rating]);

        useEffect(() => {
            // console.log(bounds)
            // if(bounds.se && bounds.nw) 


            setisLoading(true);

            // getWeatherData (coordinates.lat, coordinates.lng)
            //     .then((data) => setWeatherData(data));

            getPlacesData(type, bounds.sw, bounds.ne)
                .then((data) => {
                    setisLoading(false);
                    setfilteredPlaces([]);
                    console.log(data)
                    setPlaces(data?.filter((place) => place.name && place.num_reviews > 0));
                })
        }
            , [type, coordinates, bounds]);

        return (
            <>
                <CssBaseline />
                <Header setCoordinates={setCoordinates} />
                <Grid container spacing={3} style={{ width: '100%' }}>
                    <Grid item xs={12} md={4}>
                        <List
                            places={filteredPlaces.length ? filteredPlaces : places}
                            childClicked={childClicked}
                            isLoading={isLoading}
                            type={type}
                            setType={setType}
                            rating={rating}
                            setRating={setRating}
                        />
                        <div className="App">
                    </div>
                    </Grid>
                    <Grid item xs={12} md={8}>
                        <Map
                            setCoordinates={setCoordinates}
                            setBounds={setBounds}
                            coordinates={coordinates}
                            places={places}
                            setchildClicked={setchildClicked}
                        // weatherData={weatherData}
                        />
                    </Grid>
                </Grid>
            </>
        );
    }

    export default App;