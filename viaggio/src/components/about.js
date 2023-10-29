import React, { Fragment } from 'react';
import '../components/frontend/normalize.css';
import '../components/frontend/responsive.css';
import '../components/frontend/style.css';
import '../components/frontend/utility.css';

function About() {
    return (
        <Fragment>
                <nav className="navbar">
                    <div className="container flex">
                        <a href="index.js" className="site-brand">
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
                                    <a href="login.js" className="nav-link">login</a>
                                </li>
                                <li className="nav-item">
                                    <a href="contact.js" className="nav-link">Contact</a>
                                </li>
                            </ul>
                        </div>
                    </div>
                </nav>

                <header className="flex header-sm">
                    <div className="container">
                        <div className="header-title">
                            <h1>About</h1>
                            <p>At Viaggio we're passionate about exploring the world and helping you create unforgettable travel experiences. Whether you're a seasoned globetrotter or embarking on your very first adventure, we're here to inspire, guide, and assist you every step of the way.
                                our passion for exploration. Your adventure starts here, at Viaggio.
                                Explore. Dream. Discover.</p>
                        </div>
                    </div>
                </header>

                <section id="about" className="py-4">
                    <div className="container">
                        <div className="title-wrap">
                            <span className="sm-title">things to know about us</span>
                            <h2 className="lg-title">our story</h2>
                        </div>

                        <div className="about-row">
                            <div className="about-left my-2">
                                <img src="images/about-img.jpg" alt="about img" />
                            </div>
                            <div className="about-right">
                                <h2> Years of Experience</h2>
                                <p className="text">At Viagggio, we take pride in our years of experience in the travel industry. With decades of combined expertise, our team has navigated the globe, forging relationships with trusted partners, uncovering hidden gems, and fine-tuning the art of crafting unforgettable journeys. Our extensive background means we understand the intricacies of travel, from the thrill of discovery to the importance of seamless logistics.</p>
                                <p className="text">Our accumulated wisdom is the foundation upon which we've built Viagggio, ensuring that every traveler who chooses us receives not only an adventure but also a touch of expertise that transforms a trip into an extraordinary experience. Let our years of passion and dedication to travel enhance your journey with Viagggio</p>
                            </div>
                        </div>
                    </div>
                </section>

                <section id="facts" className="py-4 flex">
                    <div className="container">
                        <div className='title-wrap'>
                            <span className="sm-title">know some facts about our agency</span>
                            <h2 className="lg-title">fun facts</h2>
                        </div>

                        <div className="facts-row">
                            <div className="facts-item">
                                <span className="fas fa-camera-retro facts-icon"></span>
                                <div className="facts-info">
                                    <strong>1220</strong>
                                    <p className="text">photos taken</p>
                                </div>
                            </div>

                            <div className="facts-item">
                                <span className="fas fa-umbrella-beach  facts-icon"></span>
                                <div className="facts-info">
                                    <strong>450</strong>
                                    <p className="text">beaches visited</p>
                                </div>
                            </div>

                            <div className="facts-item">
                                <span className="fas fa-mountain facts-icon"></span>
                                <div className="facts-info">
                                    <strong>84</strong>
                                    <p className="text">mountains climbed</p>
                                </div>
                            </div>

                            <div className="facts-item">
                                <span className="fas fa-ship facts-icon"></span>
                                <div className="facts-info">
                                    <strong>120</strong>
                                    <p className="text">cruises organized</p>
                                </div>
                            </div>
                        </div>
                    </div>
                </section>

                <footer className="py-4">
                    <div className="container footer-row">
                        <div className="footer-item">
                            <a href="index" className="site-brand">
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
                            <h2>Popular Places:</h2>
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
        </Fragment >
    );
}

export default About;