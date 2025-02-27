import React, { useState } from 'react';
import { Autocomplete } from '@react-google-maps/api';
import { AppBar, Toolbar, /*Typography*/  InputBase, Box, Button } from '@material-ui/core';
import SearchIcon from '@material-ui/icons/Search';


import  useStyles from './styles';
import { Link } from 'react-router-dom';

const Header = ({setCoordinates}) => {
  const classes = useStyles();
  const [autocomplete, setAutocomplete] = useState(null);

  const onLoad = (autoC) => setAutocomplete(autoC);

  const onPlaceChanged = () => {
    const lat = autocomplete.getPlace().geometry.location.lat();
    const lng = autocomplete.getPlace().geometry.location.lng();

    setCoordinates({ lat, lng });

  }

  return (
     
    <AppBar  position='static'>
      <Toolbar className={classes.toolbar}>
        <Button color="default" variant='text' className={classes.title}><b>V</b><span>iaggio</span></Button>
 
       <Box display='flex'>
        {/* <Typography variant='h6' className={classes.title}>
          Explore Places
        </Typography> */}
        <Link to="/book" ><Button color="primary" variant='contained' className={classes.fhome}>Book tickets</Button></Link>
        {/* <Link><Button color="primary" variant='contained' to='/SentimentAnalysis.js' className={classes.feedback}>Feedback</Button></Link> */}
        <Autocomplete onLoad={onLoad} onPlaceChanged={onPlaceChanged}> 
          <div className={classes.search}>
            <div className={classes.searchIcon}>
              <SearchIcon/>
            </div>
            <InputBase placeholder='Search...' classes={{root: classes.inputRoot, input: classes.inputInput }} />
          </div>
        </Autocomplete>
        
        </Box>
      </Toolbar>
    </AppBar>
  );
}

export default Header;