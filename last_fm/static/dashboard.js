$(function(){
    var artistSliderTemplate = $(".artist-slider-template").html();
    var col1Template = $(".col-1-template").html();
    var col2Template = $(".col-2-template").html();
    var col3Template = $(".col-3-template").html();

    var $container = $("#container");

    function runIdleLoop()
    {
        $.ajax({
            url: "http://console.thelogin.ru/mpd/idle"
        }).done(function(){
            getStatus();
        }).fail(function(){
            setTimeout(runIdleLoop, 5000);
        });
    }
    function getStatus()
    {
        $.ajax({
            url: "http://console.thelogin.ru/mpd/status"
        }).done(function(status){
            if (status.state == "play")
            {
                $.ajax({
                    url: "http://console.thelogin.ru/mpd/current"
                }).done(function(current){
                    showMusic(current.song.artist, current.song.album, current.song.title, current.song.file);
                }).always(runIdleLoop);
            }
            else
            {
                showNoMusic();
                runIdleLoop();
            }
        }).fail(function(){
            setTimeout(getStatus, 5000);
        });
    }
    getStatus();

    // showMusic("Velvet Acid Christ", "", "Fun With Drugs", "Rave/Industrial/Velvet Acid Christ/1999 - Fun With Razors/Fun With Knives/05 - Fun With Drugs.flac");
    // showMusic("Velvet Acid Christ", "", "Decypher", "Rave/Industrial/Velvet Acid Christ/1999 - Fun With Razors/Fun With Knives/01 - Decypher.flac");
    // showMusic("Cocteau Twins", "", "In Our Angelhood", "Rock/Shoegaze/Cocteau Twins/1983 - Head Over Heels/04 - In Our Angelhood.flac");

    var currentArtist = null;
    var currentTrack = null;
    var currentPath = null;
    var artistWikiDeferred = $.Deferred();
    var lyricsDeferred = $.Deferred();
    function showMusic(artist, album, track, path)
    {
        $(".year").remove();

        var artistChanged = artist != currentArtist;
        var trackChanged = track != currentTrack;
        var pathChanged = path != currentPath;
        currentArtist = artist;
        currentTrack = track;
        currentPath = path;

        var col2deferreds = [];

        if (artistChanged)
        {
            artistWikiDeferred = $.Deferred();
            $.ajax("/dashboard/artist", {"data": {"artist": artist}}).retry({times: Number.MAX_VALUE}).done(function(artist_data){
                var $oldCol1 = $(".col-1");
                var $newCol1 = $("<div/>").addClass("col-1").hide().html(col1Template).appendTo($container);
                var $artistSlider = $newCol1.find(".artist-slider");

                shuffle(artist_data.images);
                setupArtistSlider($artistSlider, artist_data.images);

                $newCol1.fadeIn(500);
                $oldCol1.fadeOut(500, function(){
                    $oldCol1.remove();
                });

                artistWikiDeferred.resolve({"wiki": artist_data.wiki});
            });
        }

        if (artistChanged || trackChanged)
        {
            lyricsDeferred = $.Deferred();
            $.ajax("http://player.thelogin.ru/lyrics", {"data": {"artist": artist, "title": track}}).retry({times: Number.MAX_VALUE}).done(function(lyrics){
                lyricsDeferred.resolve({"lyrics": lyrics.replace(/\n/g, "<br />")});
            });
        }

        if (artistChanged || trackChanged)
        {
            $.when(artistWikiDeferred, lyricsDeferred).then(function(){
                $("#container").find(".col-2, .col-2-2").remove();

                var data = $.extend.apply($, Array.prototype.slice.call(arguments));

                function calculateHeights(container_class, callback){
                    var $container = $("<div/>").addClass(container_class).css("visibility", "hidden").appendTo("body");

                    var $cols = {};
                    $.each(data, function(k, v){
                        $cols[k] = $("<div/>").addClass("col-2").css("visibility", "hidden").html("<div>" + v + "</div>").appendTo($container);
                    });
                    setTimeout(function(){
                        var heights = {};
                        $.each($cols, function(k, v){
                            heights[k] = v.find(">div").height();
                        });

                        $container.remove();

                        callback(heights);
                    }, 0);
                }

                var totalHeight = 1060;
                var headerHeight = 69;
                var minWikiHeight = 240;
                function calculateProportionalHeights(heights)
                {
                    var wikiHeight = minWikiHeight;
                    var lyricsHeight = totalHeight - headerHeight - wikiHeight - (data["lyrics"] ? headerHeight : 0);
                    if (heights["lyrics"] < lyricsHeight)
                    {
                        wikiHeight += lyricsHeight - heights["lyrics"];
                        lyricsHeight = heights["lyrics"];                        
                    }
                    if (heights["wiki"] < wikiHeight)
                    {
                        wikiHeight = heights["wiki"];
                    }
                    return {
                        "wiki": wikiHeight,
                        "lyrics": lyricsHeight
                    };
                }

                function scaleArtistSlider()
                {
                    var $artistSlider = $(".col-1 .artist-slider");
                    var index = $artistSlider.data("$JssorSlider$").$CurrentIndex();
                    setupArtistSlider($artistSlider, $artistSlider.data("images"), index);
                }

                calculateHeights("", function(heights){
                    if (heights["lyrics"] <= totalHeight - 2 * headerHeight - minWikiHeight)
                    {
                        $container.removeClass("col-2-2");

                        setup$col2(artist, track, data, calculateProportionalHeights(heights));

                        scaleArtistSlider();
                    }
                    else
                    {
                        calculateHeights("col-2-2", function(heights){
                            $container.addClass("col-2-2");

                            var col2heights;
                            var lyricsStartInCol22;
                            if (heights["lyrics"] > totalHeight - headerHeight)
                            {
                                col2heights = calculateProportionalHeights({
                                    "wiki": heights["wiki"],
                                    "lyrics": heights["lyrics"] - totalHeight
                                });
                                lyricsStartInCol22 = false;
                            }
                            else
                            {
                                col2heights = heights;
                                lyricsStartInCol22 = true;
                            }

                            var $col2 = setup$col2(artist, track, data, col2heights);
                            if (lyricsStartInCol22)
                            {
                                $col2.find(".track-title").remove();
                                $col2.find(".track-lyrics-wrap").remove();
                            }

                            var $col2_2 = $("<div/>").addClass("col-2-2").html(col2Template).appendTo($container);

                            $col2_2.find(".artist-title").remove();
                            $col2_2.find(".artist-wiki").remove();

                            if (lyricsStartInCol22)
                            {
                                setup$colLyrics($col2_2, artist, track, data, col2heights);
                            }
                            else
                            {
                                $col2_2.find(".track-title").remove();
                                $col2_2.find(".artist-wiki-wrap").remove();
                                $col2_2.find(".track-lyrics-wrap").css("height", totalHeight);
                                $col2_2.find(".track-lyrics").css("top", -col2heights["lyrics"]).html(data["lyrics"]);

                                var $wrap1 = $col2.find(".track-lyrics-wrap");
                                var $wrap2 = $col2_2.find(".track-lyrics-wrap");
                                var visibleLyricsHeight = (parseInt($wrap1.css("height")) +
                                                           parseInt($wrap2.css("height")));
                                if (visibleLyricsHeight < heights["lyrics"])
                                {
                                    var fontScaleFactor = heights["lyrics"] / visibleLyricsHeight;
                                    var fontSize = Math.floor(parseInt($wrap1.css("fontSize")) / fontScaleFactor);
                                    $wrap1.css("fontSize", fontSize + "px");
                                    $wrap2.css("fontSize", fontSize + "px");
                                }
                            }

                            scaleArtistSlider();
                        });
                    }
                });
            });

            $.ajax("/dashboard/stats", {"data": {"artist": artist}}).retry({times: Number.MAX_VALUE}).done(function(stats){
                var $oldCol3 = $(".col-3");
                var $newCol3 = $("<div/>").addClass("col-3").hide().html(col3Template).appendTo($container);

                $newCol3.find(".album-cover").attr("src", "http://last.fm.thelogin.ru/static/covers/pad/%23191919/640/640/" +
                                                          "http/player.thelogin.ru/cover_for_file?path=" + encodeURIComponent(path));

                var $facts = $newCol3.find(".facts");
                if (stats.next_artist_get_info_interesting)
                {
                    $facts.append($("<li/>").html(stats.next_artist_get_info));
                }
                if (stats.winning_line)
                {
                    $facts.append($("<li/>").html(stats.winning_line));
                }
                if (stats.losing_line_interesting)
                {
                    $facts.append($("<li/>").html(stats.losing_line));
                }
                $facts.append($("<li/>").html(stats.next_get_info));

                $newCol3.fadeIn(500);
                $oldCol3.fadeOut(500, function(){
                    $oldCol3.remove();
                });
            });
        }
    }

    function setupArtistSlider($artistSlider, images, startIndex)
    {
        if (startIndex === undefined)
        {
            startIndex = 0;
        }

        $artistSlider.html(artistSliderTemplate);

        var $slides = $artistSlider.find(".slides");
        $.each(images, function(i, url){
            $slides.append($("<div/>").append($("<img/>").attr("u", "image").attr("src", url.replace("http:/", "/static/artists/http")))
                                      .append($("<img/>").attr("u", "thumb").attr("src", url.replace("http:/", "/static/artists/crop/77/77/http"))));
        });

        $artistSlider.find(">div").attr("id", "artist-slider");
        $artistSlider.data("images", images).data("$JssorSlider$", new $JssorSlider$("artist-slider", {
            $AutoPlay: true,
            $AutoPlayInterval: 5000,
            $PauseOnHover: 0,

            $DragOrientation: 3,
            $ArrowKeyNavigation: true,
            $SlideDuration: 800,

            $SlideshowOptions: {
                $Class: $JssorSlideshowRunner$,
                $Transitions: [{$Duration:1200,x:1,$Easing:{$Left:$JssorEasing$.$EaseInOutQuart},$Opacity:2,$Brother:{$Duration:1200,x:-1,$Easing:{$Left:$JssorEasing$.$EaseInOutQuart},$Opacity:2}}],
                $TransitionsOrder: 1,
                $ShowLink: true
            },

            $ArrowNavigatorOptions: {
                $Class: $JssorArrowNavigator$,
                $ChanceToShow: 1
            },

            $ThumbnailNavigatorOptions: {
                $Class: $JssorThumbnailNavigator$,
                $ChanceToShow: 2,

                $ActionMode: 1,
                $SpacingX: 8,
                $DisplayPieces: 10,
                $ParkingPosition: 360
            },

            $FillMode: 5,

            $StartIndex: startIndex,
        }));
    }

    function setup$col2(artist, track, data, heights)
    {
        var $col2 = $("<div/>").addClass("col-2").html(col2Template).appendTo($container);

        $col2.find(".artist-title").text(artist);
        $col2.find(".artist-wiki-wrap").css("height", heights["wiki"]);
        $col2.find(".artist-wiki").html(data["wiki"]);

        function scrollArtistWikiOrDont(immediately){
            var $artistWiki = $col2.find(".artist-wiki");

            if (localStorage.scrollArtistWiki == "true")
            {
                scrollArtistWiki(heights["wiki"], $artistWiki, immediately);
            }
            else
            {
                clearTimeout($artistWiki.data("scrollStart"));
                $artistWiki.stop().animate({ top: 0 }, 200, "swing");
            }
        }
        scrollArtistWikiOrDont(false);
        $col2.find(".artist-wiki").on("dblclick", function(event){
            localStorage.scrollArtistWiki = JSON.stringify(!JSON.parse(localStorage.scrollArtistWiki || "false"));
            scrollArtistWikiOrDont(true);
            event.preventDefault();
        });

        setup$colLyrics($col2, artist, track, data, heights)

        return $col2;
    }

    function scrollArtistWiki(height, $artistWiki, immediately)
    {
        setTimeout(function(){
            if ($artistWiki.height() > height)
            {
                var pixels = $artistWiki.height() - height;
                var animate1, animate2;
                animate1 = function(){
                    $artistWiki.animate({ top: -pixels }, pixels * 60, "linear", animate2);
                };
                animate2 = function(){
                    $artistWiki.animate({ top: 0 }, pixels / 4, "swing", animate1);
                };
                if (immediately)
                {
                    animate1();
                }
                else
                {
                    $artistWiki.data("scrollStart", setTimeout(animate1, 5000));
                }
            }
        }, 0);
    }

    function setup$colLyrics($col, artist, track, data, heights)
    {
        if (data["lyrics"])
        {
            $col.find(".track-title").text(track);
            $col.find(".track-lyrics-wrap").css("height", heights["lyrics"]);
            $col.find(".track-lyrics").html(data["lyrics"]);
        }
    }

    function shuffle(array)
    {
        var currentIndex = array.length, temporaryValue, randomIndex;

        // While there remain elements to shuffle...
        while (0 !== currentIndex)
        {
            // Pick a remaining element...
            randomIndex = Math.floor(Math.random() * currentIndex);
            currentIndex -= 1;

            // And swap it with the current element.
            temporaryValue = array[currentIndex];
            array[currentIndex] = array[randomIndex];
            array[randomIndex] = temporaryValue;
        }

        return array;
    }

    function showNoMusic()
    {
        currentArtist = null;
        currentTrack = null;
        currentPath = null;

        $.ajax("/dashboard/no_music").retry({times: Number.MAX_VALUE}).done(function(data){
            $(".col-1, .col-2, .col-2-2, .col-3").remove();

            var occupied = [[false, false, false, false], [false, false, false, false]];
            $.each(data["scrobbles_for_years"], function(k, year){
                var row, col;
                var found = false;
                for (row = 0; row < 2; row++)
                {
                    for (col = 0; col < 4; col++)
                    {
                        if (!occupied[row][col])
                        {
                            found = true;
                            break;
                        }
                    }
                    if (found)
                    {
                        break;
                    }
                }
                if (!found)
                {
                    return;
                }

                var $year = $("<div/>").addClass("year");
                $year.css("left", 480 * col).css("top", 540 * row);
                if (col % 2)
                {
                    $year.addClass("even");
                }
                occupied[row][col] = true;
                if (year["scrobbles_grouped"].length > 20)
                {
                    $year.addClass("long");
                    if (row + 1 < 2)
                    {
                        occupied[row + 1][col] = true;
                    }
                }

                $year.append($("<div/>").addClass("title").text(year["year"]));

                var $table = $("<table/>");
                /*
                $.each(year["scrobbles"], function(k, scrobble){
                    var $tr = $("<tr/>").addClass(scrobble["class"]);
                    $tr.append($("<td/>").text(scrobble["artist"] + " – " + scrobble["track"]));
                    $tr.append($("<td/>").text(scrobble["time"]));
                    $table.append($tr);
                });
                */
                $.each(year["scrobbles_grouped"], function(k, scrobble_group){
                    var $tr = $("<tr/>").addClass(scrobble_group["class"]);
                    $tr.append($("<td/>").text(scrobble_group["title"]));
                    $tr.append($("<td/>").text(scrobble_group["time"]));
                    $table.append($tr);
                });
                $year.append($table);

                $("#container").append($year);
            });
        });
    }
});
