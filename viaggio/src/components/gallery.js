import React, { Fragment } from 'react';
import '../components/frontend/normalize.css';
import '../components/frontend/responsive.css';
import '../components/frontend/style.css';
import '../components/frontend/utility.css';

function Gallery() {
    return(
        <Fragment>
        <nav className= "navbar">
            <div className= "container flex">
                <a href = "index.js" className= "site-brand">
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
                    <h1>Gallery</h1>
                    <p>Welcome to viaggio's captivating gallery, a visual voyage through the wonders of the world</p>
                </div>
            </div>
        </header>
        
        <div id = "gallery" className= "py-4">
            <div className= "container">
                <div className= "gallery-row">
                    <div className= "gallery-item shadow">
                        <img src = "./frontend/images/gallery-1.jpg" alt = "gallery img"/>
                        <span className= "zoom-icon">
                            <i className= "fas fa-search-plus"></i>
                        </span>
                    </div>
                    <div className= "gallery-item shadow">
                        <img src = "./frontend/images/gallery-2.jpg" alt = "gallery img"/>
                        <span className= "zoom-icon">
                            <i className= "fas fa-search-plus"></i>
                        </span>
                    </div>
                    <div className= "gallery-item shadow">
                        <img src = "./frontend/images/gallery-3.jpg" alt = "gallery img"/>
                        <span className= "zoom-icon">
                            <i className= "fas fa-search-plus"></i>
                        </span>
                    </div>
                    <div className= "gallery-item shadow">
                        <img src = "./frontend/images/gallery-4.jpg" alt = "gallery img"/>
                        <span className= "zoom-icon">
                            <i className= "fas fa-search-plus"></i>
                        </span>
                    </div>
                    <div className= "gallery-item shadow">
                        <img src = "./frontend/images/gallery-5.jpg" alt = "gallery img"/>
                        <span className= "zoom-icon">
                            <i className= "fas fa-search-plus"></i>
                        </span>
                    </div>
                    <div className= "gallery-item shadow">
                        <img src = "./frontend/images/gallery-6.jpg" alt = "gallery img"/>
                        <span className= "zoom-icon">
                            <i className= "fas fa-search-plus"></i>
                        </span>
                    </div>
                    <div className= "gallery-item shadow">
                        <img src = "./frontend/images/gallery-7.jpg" alt = "gallery img"/>
                        <span className= "zoom-icon">
                            <i className= "fas fa-search-plus"></i>
                        </span>
                    </div>
                    <div className= "gallery-item shadow">
                        <img src = "./frontend/images/gallery-8.jpg" alt = "gallery img"/>
                        <span className= "zoom-icon">
                            <i className= "fas fa-search-plus"></i>
                        </span>
                    </div>
                    <div className= "gallery-item shadow">
                        <img src = "./frontend/images/gallery-9.jpg" alt = "gallery img"/>
                        <span className= "zoom-icon">
                            <i className= "fas fa-search-plus"></i>
                        </span>
                    </div>
                </div>
            </div>
        </div>
        
        <div id = "img-modal-box">
            <div id = "img-modal">
                <button type = "button" id = "modal-close-btn" className= "flex">
                    <i className= "fas fa-times"></i>
                </button>
                <button type = "button" id = "prev-btn" className= "flex">
                    <i className= "fas fa-chevron-left"></i>
                </button>
                <button type = "button" id = "next-btn" className= "flex">
                    <i className= "fas fa-chevron-right"></i>
                </button>
                <img src = "./frontend/images/gallery-1.jpg" alt=''/>
            </div>
        </div>
       
        <section id = "popular" className= "py-4">
            <div className= "title-wrap">
                <span className= "sm-title">Know about some cool destinations</span>
                <h2 className= "lg-title">Popular Places</h2>
            </div>

            <div className= "popular-row">
                <div className= "popular-item shadow">
                    <img src = "./frontend/images/popular-1.jpg" alt = ""/>
                    <div>
                        <span>Eiffel Tower, Paris</span>
                        <ul className= "rating flex">
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star-half-alt"></i></li>
                            <li>&nbsp;400 reviews</li>
                        </ul>
                        <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Ducimus, quia!</p>
                    </div>
                </div>

                <div className= "popular-item shadow">
                    <img src = "./frontend/images/popular-2.jpg" alt = ""/>
                    <div>
                        <span>Machu Picchu, Peru</span>
                        <ul className= "rating flex">
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star-half-alt"></i></li>
                            <li>&nbsp;400 reviews</li>
                        </ul>
                        <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Ducimus, quia!</p>
                    </div>
                </div>

                <div className= "popular-item shadow">
                    <img src = "./frontend/images/popular-3.jpg" alt = ""/>
                    <div>
                        <span>Acropolis, Athens</span>
                        <ul className= "rating flex">
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star-half-alt"></i></li>
                            <li>&nbsp;400 reviews</li>
                        </ul>
                        <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Ducimus, quia!</p>
                    </div>
                </div>

                <div className= "popular-item shadow">
                    <img src = "./frontend/images/popular-4.jpg" alt = ""/>
                    <div>
                        <span>Bali, Indonesia</span>
                        <ul className= "rating flex">
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star-half-alt"></i></li>
                            <li>&nbsp;400 reviews</li>
                        </ul>
                        <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Ducimus, quia!</p>
                    </div>
                </div>

                <div className= "popular-item shadow">
                    <img src = "./frontend/images/popular-5.jpg" alt = ""/>
                    <div>
                        <span>Dubai, United Arab Emirates</span>
                        <ul className= "rating flex">
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star-half-alt"></i></li>
                            <li>&nbsp;400 reviews</li>
                        </ul>
                        <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Ducimus, quia!</p>
                    </div>
                </div>

                <div className= "popular-item shadow">
                    <img src = "./frontend/images/popular-6.jpg" alt = ""/>
                    <div>
                        <span>Bhutan</span>
                        <ul className= "rating flex">
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star-half-alt"></i></li>
                            <li>&nbsp;400 reviews</li>
                        </ul>
                        <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Ducimus, quia!</p>
                    </div>
                </div>

                <div className= "popular-item shadow">
                    <img src = "./frontend/images/popular-7.jpg" alt = ""/>
                    <div>
                        <span>Havana, Cuba</span>
                        <ul className= "rating flex">
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star-half-alt"></i></li>
                            <li>&nbsp;400 reviews</li>
                        </ul>
                        <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Ducimus, quia!</p>
                    </div>
                </div>

                <div className= "popular-item shadow">
                    <img src = "./frontend/images/popular-8.jpg" alt = ""/>
                    <div>
                        <span>Moskva, Russia</span>
                        <ul className= "rating flex">
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star"></i></li>
                            <li><i className= "fas fa-star-half-alt"></i></li>
                            <li>&nbsp;400 reviews</li>
                        </ul>
                        <p className= "text">Lorem ipsum dolor sit amet consectetur adipisicing elit. Ducimus, quia!</p>
                    </div>
                </div>
            </div>
        </section>
        
        <footer className= "py-4">
            <div className= "container footer-row">
                <div className= "footer-item">
                    <a href = "index.html" className= "site-brand">
                        V<span>iaggio</span>
                    </a>
                    <p className= "text">We're here to assist you with any inquiries, travel tips, or booking assistance. Reach out to us, and let's embark on your next adventure together!</p>
                </div>

                <div className= "footer-item">
                    <h2>Follow us on: </h2>
                    <ul className= "social-links">
                        <li>
                            <a href="/">
                                <i className= "fab fa-facebook-f"></i>
                            </a>
                        </li>
                        <li>
                            <a href="/">
                                <i className= "fab fa-instagram"></i>
                            </a>
                        </li>
                        <li>
                            <a href="/">
                                <i className= "fab fa-twitter"></i>
                            </a>
                        </li>
                        <li>
                            <a href="/">
                                <i className= "fab fa-pinterest"></i>
                            </a>
                        </li>
                        <li>
                            <a href="/">
                                <i className= "fab fa-google-plus"></i>
                            </a>
                        </li>
                    </ul>
                </div>

                <div className= "footer-item">
                    <h2>Popular Places:</h2>
                    <ul>
                        <li><a href="/">Thailand</a></li>
                        <li><a href="/">Australia</a></li>
                        <li><a href="/">Maldives</a></li>
                        <li><a href="/">Switzerland</a></li>
                        <li><a href="/">Germany</a></li>
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
        {/* <script>
            {`const allGalleryItem = document.querySelectorAll('.gallery-item');
            const imgModalDiv = document.getElementById('img-modal-box');
            const modalCloseBtn = document.getElementById('modal-close-btn');
            const nextBtn = document.getElementById('next-btn');
            const prevBtn = document.getElementById('prev-btn');
            let imgIndex = 0;

            allGalleryItem.forEach((galleryItem) => {
                galleryItem.addEventListener('click', () => {
                    imgModalDiv.style.display = "block";
                    let imgSrc = galleryItem.querySelector('img').src;
                    imgIndex = parseInt(imgSrc.split("-")[1].substring(0, 1));
                    showImageContent(imgIndex);
                })
            });

            // next click
            nextBtn.addEventListener('click', () => {
                imgIndex++;
                if(imgIndex > allGalleryItem.length){
                    imgIndex = 1;
                }
                showImageContent(imgIndex);
            });

            // previous click
            prevBtn.addEventListener('click', () => {
                imgIndex--;
                if(imgIndex <= 0){
                    imgIndex = allGalleryItem.length;
                }
                showImageContent(imgIndex);
            });

            function showImageContent(index){
                imgModalDiv.querySelector('#img-modal img').src = `images/gallery-${index}.jpg`;
            }

            modalCloseBtn.addEventListener('click', () => {
                imgModalDiv.style.display = "none";
            })`}
        </script> */}
        </Fragment>
    );
}

export default Gallery;