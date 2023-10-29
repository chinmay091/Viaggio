// import 'App.css';
import { alpha, makeStyles } from '@material-ui/core/styles';

export default makeStyles((theme) => ({
  title: {
    display: 'none',
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif ",
    color:'#ffff',
    fontSize:"2rem",
    [theme.breakpoints.up('sm')]: {
      display: 'block',
      // '&:hover': { backgroundColor: alpha(theme.palette.primary.light, 0.25) }
    },
  },
  
  contact: {
    display: 'none',
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif' ",
    color:'#ffff',
    fontSize:"0.9rem",
    [theme.breakpoints.up('sm')]: {
      display: 'block',
      '&:hover': { backgroundColor: alpha(theme.palette.primary.light, 0.25) }
    },
  },

  feedback: {
    display: 'none',
    fontFamily: "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif",
    color:'#ffff',
    fontSize:"0.9rem",
    [theme.breakpoints.up('sm')]: {
      display: 'block',
      '&:hover': { backgroundColor: alpha(theme.palette.primary.light, 0.25) }
    },
  },

  // Navbarbg: {
  //   position: "relative",
  //   backgroundImage: ('C:\\Users\\ASUS\\Desktop\\Viaggio\\viaggio'),
  //   overflow: "hidden",
  //   backgroundSize: "contain"
  // },
  search: {
    position: 'relative',
    borderRadius: theme.shape.borderRadius,
    backgroundColor: alpha(theme.palette.common.white, 0.15),
    '&:hover': { backgroundColor: alpha(theme.palette.common.white, 0.25) },
    marginRight: theme.spacing(2),
    marginLeft: 0,
    width: '100%',
    [theme.breakpoints.up('sm')]: { marginLeft: theme.spacing(3), width: 'auto' },
  },
  searchIcon: {
    padding: theme.spacing(0, 2), height: '100%', position: 'absolute', pointerEvents: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  inputRoot: {
    color: 'inherit',
    fontFamily:'Raleway',
    fontSize:"1.4rem",
  },
  inputInput: {
    padding: theme.spacing(1, 1, 1, 0), paddingLeft: `calc(1em + ${theme.spacing(4)}px)`, transition: theme.transitions.create('width'), width: '100%', [theme.breakpoints.up('md')]: { width: '20ch' },
    fontFamily:'Raleway',
    fontSize:"1.4rem",
  },
  toolbar: {
    display: 'flex', justifyContent: 'space-between',
  },
}));