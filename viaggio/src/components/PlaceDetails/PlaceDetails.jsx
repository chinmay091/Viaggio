import React from 'react';
import { Box, Typography, Button, Card, CardMedia, CardContent, CardActions, Chip } from '@material-ui/core';
import LocationOnIcon from '@material-ui/icons/LocationOn';
import PhoneIcon from '@material-ui/icons/Phone';
import Rating from '@material-ui/lab/Rating';

import useStyles from './styles';
import SentimentAnalysis from '../SentimentAnalysis';
const PlaceDetails = ({ place, selected, refProp }) => {

    const classes = useStyles();
    const usdtoinr = (usd) => {
        console.log(usd)
        if(usd === "$$ - $$$") {
            usd = "₹₹ - ₹₹₹"
        }
        if(usd === "$$$$") {
            usd = "₹₹₹₹"
        }
        return usd
    }

    if(selected) refProp?.current?.scrollIntoView({ behavious: 'smooth', block: 'start'})

  return (
        <Card elevation={6}>
            <CardMedia 
            style={{ height: 350 }}
            image={place.photo ? place.photo.images.large.url : 'https://www.foodserviceandhospitality.com/wp-content/uploads/2016/09/Restaurant-Placeholder-001.jpg' }
            title= {place.name}
            />
                <CardContent>
                    <Typography gutterbottom variant='h5'>{place.name}</Typography>
                    <Box display='flex' justifyContent='space-between'>
                        <Rating  value={Number(place.rating)} readOnly />
                        <Typography gutterBottom variant='subtitle1'>Out of {place.num_reviews} reviews</Typography>
                    </Box>
                    <Box display='flex' justifyContent='space-between'>
                        <Typography variant='subtitle1'>Price</Typography>
                        <Typography gutterBottom variant='subtitle1'>{usdtoinr(place.price_level)}</Typography>
                    </Box>
                    <Box display='flex' justifyContent='space-between'>
                        <Typography variant='subtitle1'>Rank</Typography>
                        <Typography gutterBottom variant='subtitle1'>{place.ranking}</Typography>
                    </Box>
                    {place?.awards?.map((award) => (
                        <Box display="flex" justifyContent="space-between" my={1} alignItems="center">
                            <img src={award.images.small} alt={award.display_name} />
                            <Typography variant="subtitle2" color="textSecondary">{award.display_name}</Typography>
                        </Box>
                    ))}
                    {place?.cuisine?.map(({name}) => (
                        <Chip key={name} size='small' label={name} className={classes.chip} />
                    ))}
                    {place?.address && (
                        <Typography  gutterBottom variant='body2' color='textSecondary' className={classes.subtitle}>
                            <LocationOnIcon /> {place.address}
                        </Typography>
                    )}
                    {place?.phone && (
                        <Typography  gutterBottom variant='body2' color='textSecondary' className={classes.spacing}>
                            <PhoneIcon /> {place.phone}
                        </Typography>
                    )}
                    <CardActions>
                        <Button size='small' color='primary' onClick={() => window.open(place.web_url, '_blank')}>
                            Trip Advisor
                        </Button>
                        <Button size='small' color='primary' onClick={() => window.open(place.website, '_blank')}>
                            Website
                        </Button>
                        
                    </CardActions>
                    <SentimentAnalysis />
                </CardContent>
             </Card>
  )
}

export default PlaceDetails;