import React, { Fragment } from 'react';
import '../components/frontend/normalize.css';
import '../components/frontend/responsive.css';
import '../components/frontend/style.css';
import '../components/frontend/utility.css';

function Contact() {
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
                                <a href="login.js" className="nav-link">Login</a>
                            </li>
                            <li className="nav-item">
                                <a href="contac.js" className="nav-link">Contact</a>
                            </li>
                        </ul>
                    </div>
                </div>
            </nav>

            <header className="flex header-sm">
                <div className="container">
                    <div className="header-title">
                        <h1>Contact us</h1>


                    </div>
                </div>
            </header>

            <section id="contact" className="py-4">
                <div className="container">
                    <div className="title-wrap">
                        <span className="sm-title">get in touch with us</span>
                        <h2 className="lg-title"></h2>
                    </div>

                    <div className="contact-row">
                        <div className="contact-left">
                            <form className="contact-form">
                                <input type="text" className="form-control" placeholder="Your name" />
                                <input type="email" className="form-control" placeholder="Your email" />
                                <textarea rows="4" className="form-control" placeholder="Your message" style={{ resize: "none" }}></textarea>
                                <input type="submit" className="btn" value="Send message" />
                            </form>
                        </div>
                        <div className="contact-right my-2">
                            <div className="contact-item">
                                <span className="contact-icon flex">
                                    <i className="fa fa-phone-alt"></i>
                                </span>
                                <div>
                                    <span>Phone</span>
                                    <p className="text">+91 9876543210</p>
                                </div>
                            </div>
                            <div className="contact-item">
                                <span className="contact-icon flex">
                                    <a href="https://www.google.com/maps/place/McDonald's/@19.233136,72.8379791,17z/data=!3m1!5s0x3be7b12f8e0383fd:0xa3579664fdee3144!4m6!3m5!1s0x3be7b1376442a551:0xb58484eb2bf7a98!8m2!3d19.2304274!4d72.840668!16s%2Fg%2F11h5mfnzhz?entry=ttu" target="_blank"><i className="fa fa-map-marked-alt"></i></a>
                                </span>
                                <div>
                                    <span>Address</span>
                                    <p className="text">102 Vazira Mcd , Mumbai</p>
                                </div>
                            </div>
                            <div className="contact-item">
                                <span className="contact-icon flex">
                                    <i className="fa fa-envelope"></i>
                                </span>
                                <div>
                                    <span>Message</span>
                                    <p className="text">info@viaggio.com</p>
                                </div>
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
                            <li><a href="https://www.tourismthailand.org/home">Thailand</a></li>
                            <li><a href="https://www.australia.com/en-in/facts-and-planning.html?cid=paid-search|in|SYD798|brand|Google||||||||||&ef_id=CjwKCAjwnOipBhBQEiwACyGLumkPYgFBgZHVnxUz1iPKnM4q6sENXAH0Xmk_WhyijVTkfyfkdcWkyRoCgAgQAvD_BwE:G:s&s_kwcid=AL!4635!3!445369800619!e!!g!!holiday%20in%20australia!9509291246!100011232474&utm_actcampaign=9509291246&gad=1">Australia</a></li>
                            <li><a href="https://visitmaldives.com/en">Maldives</a></li>
                            <li><a href="https://www.myswitzerland.com/en-in/">Switzerland</a></li>
                            <li><a href="https://www.germany.travel/en/home.html">Germany</a></li>
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
        </Fragment>
    )
}

export default Contact;