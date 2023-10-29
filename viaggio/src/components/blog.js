import React, { Fragment } from 'react';
import '../components/frontend/normalize.css';
import '../components/frontend/responsive.css';
import '../components/frontend/style.css';
import '../components/frontend/utility.css';

function Blog() {
    return(
        <Fragment>
        <nav className= "navbar">
            <div className= "container flex">
                <a href = "index" className= "site-brand">
                    V<span>iaggio</span>
                </a>

                <button type = "button" id = "navbar-show-btn" className= "flex">
                    <i className= "fas fa-bars"></i>
                </button>
                <div id = "navbar-collapse">
                    <button type = "button" id = "navbar-close-btn" className= "flex">
                        <i className= "fas fa-times"></i>
                    </button>
                    <ul className= "navbar-nav">
                        <li className= "nav-item">
                            <a href = "index.js" className= "nav-link">Home</a>
                        </li>
                        <li className= "nav-item">
                            <a href = "gallery.js" className= "nav-link">Gallery</a>
                        </li>
                        <li className= "nav-item">
                            <a href = "blog.js" className= "nav-link">Blog</a>
                        </li>
                        <li className= "nav-item">
                            <a href = "about.js" className= "nav-link">About</a>
                        </li>
                        <li className= "nav-item">
                            <a href = "login.js" className= "nav-link">login</a>
                        </li>
                        <li className= "nav-item">
                            <a href = "contact.js" className= "nav-link">Contact</a>
                        </li>
                    </ul>
                </div>
            </div>
        </nav>
        
        <header className= "flex header-sm">
            <div className= "container">
                <div className= "header-title">
                    <h1>Blog</h1>
                    <p>Welcome to the heart and soul of our travel app, our blog page</p>
                </div>
            </div>
        </header>
        
        <section id = "blog" className= "py-4">
            <div className= "container">
                <div className= "title-wrap">
                    <h2 className= "sm-title">read these blog for information</h2>
                    <h3 className= "lg-title">recent blog</h3>
                </div>

                <div className= "blog-row">
                    <div className= "blog-item my-2 shadow">
                        <div className= "blog-item-top">
                            <img src = "images/blog-1.jpg" alt = "blog"/>
                            <span className= "blog-date">oct 28, 2021</span>
                        </div>
                        <div className= "blog-item-bottom">
                            <span>travel | john doe</span>
                            <a  href = "/">Lorem, ipsum dolor sit amet consectetur adipisicing elit?</a>
                            <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Distinctio voluptatem nulla harum accusantium tempora dicta quas quod id, repellat temporibus illo libero explicabo laboriosam.</p>
                        </div>
                    </div>

                    <div className= "blog-item my-2 shadow">
                        <div className= "blog-item-top">
                            <img src = "images/blog-2.jpg" alt = "blog"/>
                            <span className= "blog-date">oct 28, 2021</span>
                        </div>
                        <div className= "blog-item-bottom">
                            <span>travel | john doe</span>
                            <a  href = "/">Lorem, ipsum dolor sit amet consectetur adipisicing elit?</a>
                            <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Distinctio voluptatem nulla harum accusantium tempora dicta quas quod id, repellat temporibus illo libero explicabo laboriosam.</p>
                        </div>
                    </div>

                    <div className= "blog-item my-2 shadow">
                        <div className= "blog-item-top">
                            <img src = "images/blog-3.jpg" alt = "blog"/>
                            <span className= "blog-date">oct 28, 2021</span>
                        </div>
                        <div className= "blog-item-bottom">
                            <span>travel | john doe</span>
                            <a  href = "/">Lorem, ipsum dolor sit amet consectetur adipisicing elit?</a>
                            <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Distinctio voluptatem nulla harum accusantium tempora dicta quas quod id, repellat temporibus illo libero explicabo laboriosam.</p>
                        </div>
                    </div>

                    <div className= "blog-item my-2 shadow">
                        <div className= "blog-item-top">
                            <img src = "images/blog-4.jpg" alt = "blog"/>
                            <span className= "blog-date">oct 28, 2021</span>
                        </div>
                        <div className= "blog-item-bottom">
                            <span>travel | john doe</span>
                            <a  href = "/">Lorem, ipsum dolor sit amet consectetur adipisicing elit?</a>
                            <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Distinctio voluptatem nulla harum accusantium tempora dicta quas quod id, repellat temporibus illo libero explicabo laboriosam.</p>
                        </div>
                    </div>

                    <div className= "blog-item my-2 shadow">
                        <div className= "blog-item-top">
                            <img src = "images/blog-5.jpg" alt = "blog"/>
                            <span className= "blog-date">oct 28, 2021</span>
                        </div>
                        <div className= "blog-item-bottom">
                            <span>travel | john doe</span>
                            <a  href = "/">Lorem, ipsum dolor sit amet consectetur adipisicing elit?</a>
                            <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Distinctio voluptatem nulla harum accusantium tempora dicta quas quod id, repellat temporibus illo libero explicabo laboriosam.</p>
                        </div>
                    </div>

                    <div className= "blog-item my-2 shadow">
                        <div className= "blog-item-top">
                            <img src = "images/blog-6.jpg" alt = "blog"/>
                            <span className= "blog-date">oct 28, 2021</span>
                        </div>
                        <div className= "blog-item-bottom">
                            <span>travel | john doe</span>
                            <a  href = "/">Lorem, ipsum dolor sit amet consectetur adipisicing elit?</a>
                            <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Distinctio voluptatem nulla harum accusantium tempora dicta quas quod id, repellat temporibus illo libero explicabo laboriosam.</p>
                        </div>
                    </div>

                    <div className= "blog-item my-2 shadow">
                        <div className= "blog-item-top">
                            <img src = "images/blog-7.jpg" alt = "blog"/>
                            <span className= "blog-date">oct 28, 2021</span>
                        </div>
                        <div className= "blog-item-bottom">
                            <span>travel | john doe</span>
                            <a  href = "/">Lorem, ipsum dolor sit amet consectetur adipisicing elit?</a>
                            <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Distinctio voluptatem nulla harum accusantium tempora dicta quas quod id, repellat temporibus illo libero explicabo laboriosam.</p>
                        </div>
                    </div>

                    <div className= "blog-item my-2 shadow">
                        <div className= "blog-item-top">
                            <img src = "images/blog-8.jpg" alt = "blog"/>
                            <span className= "blog-date">oct 28, 2021</span>
                        </div>
                        <div className= "blog-item-bottom">
                            <span>travel | john doe</span>
                            <a  href = "/">Lorem, ipsum dolor sit amet consectetur adipisicing elit?</a>
                            <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Distinctio voluptatem nulla harum accusantium tempora dicta quas quod id, repellat temporibus illo libero explicabo laboriosam.</p>
                        </div>
                    </div>
                </div>
            </div>
        </section>
        
        <footer className= "py-4">
            <div className= "container footer-row">
                <div className= "footer-item">
                    <a href = "index" className= "site-brand">
                        V<span>iaggio</span>
                    </a>
                    <p className= "text">We're here to assist you with any inquiries, travel tips, or booking assistance. Reach out to us, and let's embark on your next adventure together!</p>
                </div>

                <div className= "footer-item">
                    <h2>Follow us on: </h2>
                    <ul className= "social-links">
                        <li>
                            <a  href = "/">
                                <i className= "fab fa-facebook-f"></i>
                            </a>
                        </li>
                        <li>
                            <a href = "/">
                                <i className= "fab fa-instagram"></i>
                            </a>
                        </li>
                        <li>
                            <a href = "/">
                                <i className= "fab fa-twitter"></i>
                            </a>
                        </li>
                        <li>
                            <a href = "/">
                                <i className= "fab fa-pinterest"></i>
                            </a>
                        </li>
                        <li>
                            <a href = "/">
                                <i className= "fab fa-google-plus"></i>
                            </a>
                        </li>
                    </ul>
                </div>

                <div className= "footer-item">
                    <h2>Popular Places:</h2>
                    <ul>
                        <li><a href = "/">Thailand</a></li>
                        <li><a href = "/">Australia</a></li>
                        <li><a href = "/">Maldives</a></li>
                        <li><a href = "/">Switzerland</a></li>
                        <li><a href = "/">Germany</a></li>
                    </ul>
                </div>

                <div className= "subscribe-form footer-item">
                    <h2>Subscribe for Newsletter!</h2>
                    <form className= "flex">
                        <input type = "email" placeholder="Enter Email" className= "form-control"/>
                        <input type = "submit" className= "btn" value = "Subscribe"/>
                    </form>
                </div>
            </div>
        </footer>
        
        <script src="./frontend/js/script.js"></script>
        
        </Fragment>
    );
}


export default Blog;