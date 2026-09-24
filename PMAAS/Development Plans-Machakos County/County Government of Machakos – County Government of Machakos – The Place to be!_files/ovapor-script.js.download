(function( $ ){
	'use strict';

    // Document ready
	$(document).ready( function() {
        // Load more button
        $('.ova-load-more-por').on( 'click', function() {
            var paged   = $(this).closest('.ova_more_por').attr('data-paged');
            var perpage = $(this).closest('.ova_more_por').attr('data-perpage');
            var cat     = $(this).closest('.ova_more_por').attr('data-cat');
            var type    = $(this).closest('.ova_more_por').attr('data-type');

            var new_paged = parseInt(paged) + 1;
            $(this).closest('.ova_more_por').attr('data-paged',new_paged);

            $('.ova-load-more-por').css({'display':'none'});
            $('.ova-loader').css({'display':'inline-block'});

            jQuery.ajax({
                url: ajax_object.ajax_url,
                type: 'POST',
                data: ({
                    action: 'ova_loadmore_portfolio',
                    paged: paged,
                    perpage: perpage,
                    cat: cat,
                    type: type,
                }),
                success: function(data) {
                    if ( data ){
                        $('.content-por').append(data).isotope('appended', data);

                        $('.content-por').imagesLoaded( function() {
                            $('.content-por').isotope( 'reloadItems' ).isotope();
                        });

                        $('.ova-load-more-por').css({'display':'inline-block'});
                        $('.ova-loader').css({'display':'none'});
                    } else {
                        $('.ova-loader').css({'display':'none'});
                        $('.ova-nodata').css({'display':'block'});
                        $('.ova-nodata span').css({'display':'inline-block'});
                    }
                }
            });
        }); // End load more button

        // Images loaded
        $(".content-por").each(function(){
            var $mcontainer = $(this);
            $mcontainer.imagesLoaded( function() {
                $mcontainer.isotope({
                    itemSelector : '.ovapor-item',
                    animationOptions: {
                        duration: 750,
                        easing: 'linear'
                    },
                });

                if ( $mcontainer.hasClass('classic-portfolio') ) {
                    $mcontainer.isotope({
                        layoutMode: 'fitRows',
                        fitRows: {
                        gutter: 30
                        },
                    })
                }
            });
        }); // End Images loaded

        // Archive portfolio
        $('.archive-por .list-cat-por li').click( function() {
            // Remove active class
            $(".archive-por .list-cat-por li").removeClass("active");

            // Add active class
            $(this).addClass("active");    

            // Date filter
            var selector = $(this).attr('data-filter'); 

            // isotope
            $(".content-por").isotope({ 
                filter: selector, 
                animationOptions: { 
                    duration: 750, 
                    easing: 'linear', 
                    queue: false, 
                } 
            }); 

            // isotope - template: classic
            if ( $(this).hasClass('classic-portfolio') ) {
                $(".content-por").isotope({
                    layoutMode: 'fitRows',
                    fitRows: {
                        gutter: 30
                    }
                });
            }

            return false; 
        }); // End Archive portfolio

        // Gallery fancybox
        $('.single-por .item-gallery .por-gallery-fancybox').on( 'click', function(e) {
            e.preventDefault();

            var index       = $(this).data('index');
            var galleryData = $(this).closest('.single-por').find('.ova-data-gallery').data('gallery');

            Fancybox.show( galleryData, {
                Image: {
                    Panzoom: {
                        zoomFriction: 0.7,
                        maxScale: function () {
                            return 3;
                        },
                    },
                },
                startIndex: index,
            });
        }); // End Gallery fancybox
    }); // End Document ready

})(jQuery); 	