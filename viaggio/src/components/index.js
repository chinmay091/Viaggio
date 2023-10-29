import React, { Fragment } from 'react';
import { useNavigate } from 'react-router-dom';
import '../components/frontend/normalize.css';
import '../components/frontend/responsive.css';
import '../components/frontend/style.css';
import '../components/frontend/utility.css';

// import './frontend/images';


function Index() {

    const navigate = useNavigate();
    function redirect() {
        navigate('/App');

    }

    return (


        <Fragment>
            <div>
                {/* <script>
                function redirect(){
                    window.location.href = "/"
                }   
            </script> */}

                <nav className="navbar">
                    <div className="container flex">
                        <a href="/" className="site-brand">
                            V<span>iaggio</span>
                        </a>

                        <button type="button" id="navbar-show-btn" className="flex">
                            <i className="fas fa-bars"></i>
                        </button>
                        <div id="navbar-collapse">
                            <button type="button" id="navbar-close-btn" className="flex">
                                <i className="fas fa-times"></i>
                            </button>
                            <ul className="navbar-nav">
                                <li className="nav-item">
                                    <a href="index.js" className="nav-link">Home</a>
                                </li>
                                <li className="nav-item">
                                    <a href="gallery.js" className="nav-link">Gallery</a>
                                </li>
                                <li className="nav-item">
                                    <a href="blog.js" className="nav-link">Blog</a>
                                </li>
                                <li className="nav-item">
                                    <a href="about.js" className="nav-link">About</a>
                                </li>
                                <li className="nav-item">
                                    <a href="login.js" className="nav-link">Login</a>
                                </li>
                                <li className="nav-item">
                                    <a href="contact.js" className="nav-link">Contact</a>
                                </li>
                            </ul>
                        </div>
                    </div>
                </nav>

                <header className="flex" >
                    <div className="container" >
                        <div className="header-title">
                            <h1 >Leave Your Footprints</h1>
                            <p>Embark on a journey beyond imagination with Viaggio.</p>
                            <div className="header-form">
                                <h2>Choose your Travel location</h2>
                                <form className="flex">
                                    {/* <!-- <input type="text" className="form-control" placeholder="Destination name">
                                    <input type="date" className="form-control" placeholder="Date">
                                        <input type="number" className="form-control" placeholder="Price (₹)"> --> */}
                                    <button className="btn" onClick={redirect}> Buon viaggio... </button>
                                </form>
                            </div>
                        </div>
                    </div>
                </header>


                
                <section id="featured" className="py-4">
                    <div className="container">
                        <div className="title-wrap">
                            <span className="sm-title">know about some places before your travel</span>
                            <h2 className="lg-title">featured places</h2>
                        </div>

                        <div className="featured-row">
                            <div className="featured-item my-2 shadow">
                                <img src="./frontend/images/featured-reo-de-janeiro-brazil.jpg" alt="featured place" />
                                <div className="featured-item-content">
                                    <span>
                                        <i className="fas fa-map-marker-alt"></i>
                                        Rio De Janeiro, Brazil
                                    </span>
                                    <div>
                                        <p className="text">Rio de Janeiro is a huge seaside city in Brazil, famed for its Copacabana and Ipanema beaches</p>
                                    </div>
                                </div>
                            </div>

                            <div className="featured-item my-2 shadow">
                                <img src="/frontend/images/featured-north-bondi-australia.jpg" alt="featured place" />
                                <div className="featured-item-content">
                                    <span>
                                        <i className="fas fa-map-marker-alt"></i>
                                        North Bondi, Australia
                                    </span>
                                    <div>
                                        <p className="text">Lorem ipsum, dolor sit amet consectetur adipisicing elit. Dicta sed dignissimos libero soluta illum, harum amet excepturi sit?</p>
                                    </div>
                                </div>
                            </div>

                            <div className="featured-item my-2 shadow">
                                <img src="/frontend/images/featured-berlin-germany.jpg" alt="featured place" />
                                <div className="featured-item-content">
                                    <span>
                                        <i className="fas fa-map-marker-alt"></i>
                                        Berlin, Germany
                                    </span>
                                    <div>
                                        <p className="text">Lorem ipsum, dolor sit amet consectetur adipisicing elit. Dicta sed dignissimos libero soluta illum, harum amet excepturi sit?</p>
                                    </div>
                                </div>
                            </div>

                            <div className="featured-item my-2 shadow">
                                <img src="/frontend/images/featured-khwaeng-wat-arun-thailand.jpg" alt="featured place" />
                                <div className="featured-item-content">
                                    <span>
                                        <i className="fas fa-map-marker-alt"></i>
                                        Khwaeng wat arun, thailand
                                    </span>
                                    <div>
                                        <p className="text">Lorem ipsum, dolor sit amet consectetur adipisicing elit. Dicta sed dignissimos libero soluta illum, harum amet excepturi sit?</p>
                                    </div>
                                </div>
                            </div>

                            <div className="featured-item my-2 shadow">
                                <img src="/frontend/images/featured-rome-italy.jpg" alt="featured place" />
                                <div className="featured-item-content">
                                    <span>
                                        <i className="fas fa-map-marker-alt"></i>
                                        Rome, Italy
                                    </span>
                                    <div>
                                        <p className="text">Lorem ipsum, dolor sit amet consectetur adipisicing elit. Dicta sed dignissimos libero soluta illum, harum amet excepturi sit?</p>
                                    </div>
                                </div>
                            </div>

                            <div className="featured-item my-2 shadow">
                                <img src="/frontend/images/featured-fuvahmulah-maldives.jpg" alt="featured place" />
                                <div className="featured-item-content">
                                    <span>
                                        <i className="fas fa-map-marker-alt"></i>
                                        fuvahmulah, maldives
                                    </span>
                                    <div>
                                        <p className="text">Lorem ipsum, dolor sit amet consectetur adipisicing elit. Dicta sed dignissimos libero soluta illum, harum amet excepturi sit?</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                <section id="services" className="py-4">
                    <div className="container">
                        <div className="title-wrap">
                            <span className="sm-title">know about services that we offer</span>
                            <h2 className="lg-title">Our services</h2>
                        </div>

                        <div className="services-row">
                            <div className="services-item">
                                <span className="services-icon">
                                    <i className="fas fa-hotel"></i>
                                </span>
                                <h3>Luxurious Hotel</h3>
                                <p className="text">Lorem ipsum dolor sit amet, consectetur adipisicing elit. Quidem quo, totam repellat velit, dignissimos sequi error a minima architecto fugit nisi dolorum repellendus?</p>
                                <a href="/" className="btn">Read more</a>
                            </div>

                            <div className="services-item">
                                <span className="services-icon">
                                    <i className="fas fa-map-marked-alt"></i>
                                </span>
                                <h3>Trave Guide</h3>
                                <p className="text">Lorem ipsum dolor sit amet, consectetur adipisicing elit. Quidem quo, totam repellat velit, dignissimos sequi error a minima architecto fugit nisi dolorum repellendus?</p>
                                <a href="/" className="btn">Read more</a>
                            </div>

                            <div className="services-item">
                                <span className="services-icon">
                                    <i className="fas fa-money-bill"></i>
                                </span>
                                <h3>Suitable Price</h3>
                                <p className="text">Lorem ipsum dolor sit amet, consectetur adipisicing elit. Quidem quo, totam repellat velit, dignissimos sequi error a minima architecto fugit nisi dolorum repellendus?</p>
                                <a href="/" className="btn">Read more</a>
                            </div>
                        </div>
                    </div>
                </section>

                <section id="testimonials" className="py-4">
                    <div className="container">
                        <div className="title-wrap">
                            <span className="sm-title">what our clients say about us</span>
                            <h2 className="lg-title">testimonials</h2>
                        </div>

                        <div className="test-row">
                            <div className="test-item">
                                <p className="text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Assumenda blanditiis, asperiores, velit iste eos officiis tempora magni quaerat quo consectetur expedita cum recusandae facere nam voluptate minus iusto eum. Delectus!</p>
                                <div className="test-item-info">
                                    <img src="/frontend/images/test-1.jpg" alt="testimonial" />
                                    <div>
                                        <h3>Kevin Wilson</h3>
                                        <p className="text">Trip to Brazil</p>
                                    </div>
                                </div>
                            </div>

                            <div className="test-item">
                                <p className="text">Lorem ipsum, dolor sit amet consectetur adipisicing elit. Sed ut dolores tenetur harum deserunt. Maxime tenetur consectetur recusandae nobis fugit iusto natus quibusdam nulla!</p>
                                <div className="test-item-info">
                                    <img src="/frontend/images/test-2.jpg" alt="testimonial" />
                                    <div>
                                        <h3>Ben Davis</h3>
                                        <p className="text">Trip to Maldives</p>
                                    </div>
                                </div>
                            </div>

                            <div className="test-item">
                                <p className="text">Lorem ipsum dolor sit, amet consectetur adipisicing elit. Quidem sapiente amet expedita quae autem deleniti quo magni numquam facilis soluta dicta, praesentium ipsum, quos optio sed quibusdam! Reprehenderit recusandae provident id nemo!</p>
                                <div className="test-item-info">
                                    <img src="/frontend/images/test-3.jpg" alt="testimonial" />
                                    <div>
                                        <h3>Jaura Jones</h3>
                                        <p className="text">Trip to Thailand</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                <section id="video">
                    <div className="video-wrapper flex">
                        <video loop>
                            <source src="/frontend/videos/video-section.mp4" type="video/mp4" />
                        </video>
                        <button type="button" id="play-btn">
                            <i className="fas fa-play"></i>
                        </button>
                    </div>
                </section>

                <footer className="py-4">
                    <div className="container footer-row">
                        <div className="footer-item">
                            <a href="index.html" className="site-brand">
                                V<span>iaggio</span>
                            </a>
                            <p className="text">We're here to assist you with any inquiries, travel tips, or booking assistance. Reach out to us, and let's embark on your next adventure together!</p>
                        </div>

                        <div className="footer-item">
                            <h2>Follow us on: </h2>
                            <ul className="social-links">
                                <li>
                                    <a href="/">
                                        <i className="fab fa-facebook-f"></i>
                                    </a>
                                </li>
                                <li>
                                    <a href="/">
                                        <i className="fab fa-instagram"></i>
                                    </a>
                                </li>
                                <li>
                                    <a href="/">
                                        <i className="fab fa-twitter"></i>
                                    </a>
                                </li>
                                <li>
                                    <a href="/">
                                        <i className="fab fa-pinterest"></i>
                                    </a>
                                </li>
                                <li>
                                    <a href="/">
                                        <i className="fab fa-google-plus"></i>
                                    </a>
                                </li>
                            </ul>
                        </div>

                        <div className="footer-item">
                            <h2>Popular Places</h2>
                            <ul>
                                <li><a href="/">Thailand</a></li>
                                <li><a href="/">Australia</a></li>
                                <li><a href="/">Maldives</a></li>
                                <li><a href="/">Switzerland</a></li>
                                <li><a href="/">Germany</a></li>
                            </ul>
                        </div>

                        <div className="subscribe-form footer-item">
                            <h2>Subscribe for Newsletter!</h2>
                            <form className="flex">
                                <input type="email" placeholder="Enter Email" className="form-control" />
                                <input type="submit" className="btn" value="Subscribe" />
                            </form>
                        </div>
                    </div>
                </footer>

                <script src="./frontend/js/script.js"></script>
                <script>
                    {`
                let video = document.querySelector('.video-wrapper video');
                document.getElementById('play-btn').addEventListener('click', () => {
                    if(video.paused){
                        video.play()
                    } else {
                        video.pause()
                    }
                });
                `}
                </script>
                <button onClick={redirect}>Go to App</button>
            </div>
        </Fragment>
    );
}

export default Index;